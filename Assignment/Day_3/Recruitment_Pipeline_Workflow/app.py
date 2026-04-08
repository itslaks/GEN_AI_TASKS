"""
╔══════════════════════════════════════════════════════════════════╗
║         RECRUITER.AI — LangGraph Recruitment Pipeline            ║
║         Flask API + LangGraph + Groq (llama-3.1-8b-instant)     ║
╚══════════════════════════════════════════════════════════════════╝
Single-file backend: Flask API + LangGraph workflow + Resume Chatbot
"""

from __future__ import annotations
import os, json, uuid, hashlib, random, re
from datetime import datetime, timedelta
from typing import TypedDict, Annotated, List, Optional
from functools import lru_cache
import operator

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ─────────────────────────────────────────────
# LangGraph / LangChain imports
# ─────────────────────────────────────────────
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_community.llms import Ollama

# ─────────────────────────────────────────────
# LLM Setup — Groq primary, Mistral fallback
# ─────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
PRIMARY_MODEL = "llama-3.1-8b-instant"
FALLBACK_MODEL = "mistral"

def get_llm():
    """Get primary (Groq) or fallback (local Mistral) LLM."""
    if GROQ_API_KEY:
        try:
            return ChatGroq(
                groq_api_key=GROQ_API_KEY,
                model_name=PRIMARY_MODEL,
                temperature=0.2,
                max_tokens=2048,
            )
        except Exception as e:
            print(f"[LLM] Groq init failed: {e}. Falling back to local Mistral.")
    try:
        return Ollama(model=FALLBACK_MODEL, temperature=0.2)
    except Exception:
        raise RuntimeError("No LLM available. Set GROQ_API_KEY or run local Mistral via Ollama.")

# ─────────────────────────────────────────────
# State Schema (TypedDict)
# ─────────────────────────────────────────────
class ScreenedCandidate(TypedDict):
    candidate_id: str
    name: str
    score: float
    matched_skills: List[str]
    missing_skills: List[str]
    status: str          # "shortlisted" | "rejected" | "needs_clarification"
    reason: str
    resume_text: str

class SchedulingRequest(TypedDict):
    candidate_id: str
    name: str
    preferred_slots: List[str]
    conflict: bool

class InterviewSlot(TypedDict):
    candidate_id: str
    name: str
    confirmed_time: str
    interviewer: str
    meeting_link: str

class InterviewNote(TypedDict):
    candidate_id: str
    notes: str
    raw_input: str

class Evaluation(TypedDict):
    candidate_id: str
    name: str
    final_decision: str   # "hire" | "hold" | "reject"
    confidence: float
    rubric_scores: dict
    summary: str
    needs_human_review: bool

class AuditEntry(TypedDict):
    timestamp: str
    node: str
    candidate_id: Optional[str]
    event: str
    details: str

class RecruitmentState(TypedDict):
    job_id: str
    job_description: str
    resumes: List[dict]                          # raw resumes
    screened_candidates: Annotated[List[ScreenedCandidate], operator.add]
    scheduling_requests: List[SchedulingRequest]
    interview_slots: List[InterviewSlot]
    interview_notes: List[InterviewNote]
    evaluations: Annotated[List[Evaluation], operator.add]
    audit_log: Annotated[List[AuditEntry], operator.add]
    clarification_needed: List[str]              # candidate_ids needing clarification
    scheduling_retries: dict                      # candidate_id -> retry_count
    error: Optional[str]

# ─────────────────────────────────────────────
# Audit helper
# ─────────────────────────────────────────────
def make_audit(node: str, event: str, details: str, candidate_id: str = None) -> AuditEntry:
    return AuditEntry(
        timestamp=datetime.utcnow().isoformat() + "Z",
        node=node,
        candidate_id=candidate_id,
        event=event,
        details=details,
    )

# ─────────────────────────────────────────────
# STUB TOOLS  (deterministic, no LLM)
# ─────────────────────────────────────────────
def calendar_api_check_availability(candidate_id: str, slots: List[str]) -> dict:
    """Stub: simulates calendar conflict detection."""
    has_conflict = random.random() < 0.25  # 25% chance of conflict
    available = [s for s in slots if not has_conflict or random.random() > 0.4]
    return {"candidate_id": candidate_id, "available_slots": available, "conflict": has_conflict and not available}

def calendar_api_book_slot(candidate_id: str, slot: str) -> dict:
    """Stub: books an interview slot, returns meeting link."""
    meeting_id = hashlib.md5(f"{candidate_id}{slot}".encode()).hexdigest()[:8]
    return {
        "confirmed": True,
        "meeting_link": f"https://meet.recruiter.ai/room/{meeting_id}",
        "interviewer": random.choice(["Sarah Chen", "Marcus Rivera", "Priya Nair", "Tom Adler"]),
    }

def dedupe_by_candidate_id(candidates: List[dict]) -> List[dict]:
    """Idempotency: deduplicate resumes by candidate_id."""
    seen = set()
    result = []
    for c in candidates:
        cid = c.get("candidate_id") or hashlib.md5(c.get("text","").encode()).hexdigest()[:12]
        c["candidate_id"] = cid
        if cid not in seen:
            seen.add(cid)
            result.append(c)
    return result

def parse_score_from_text(text: str) -> float:
    """Deterministic: extract first numeric score (0-100) from LLM output."""
    matches = re.findall(r'\b(\d{1,3}(?:\.\d+)?)\b', text)
    for m in matches:
        val = float(m)
        if 0 <= val <= 100:
            return val
    return 50.0

def parse_confidence_from_text(text: str) -> float:
    """Deterministic: extract confidence score."""
    matches = re.findall(r'confidence[:\s]+(\d{1,3}(?:\.\d+)?)', text, re.IGNORECASE)
    if matches:
        return min(float(matches[0]) / 100.0, 1.0)
    return 0.7

def extract_decision(text: str) -> str:
    text_lower = text.lower()
    if "strong hire" in text_lower or "definitely hire" in text_lower:
        return "hire"
    if any(w in text_lower for w in ["hire", "recommend", "offer"]):
        return "hire"
    if any(w in text_lower for w in ["hold", "waitlist", "maybe", "consider later"]):
        return "hold"
    return "reject"

# ─────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────
RESUME_SCREENING_PROMPT = """You are an expert technical recruiter AI. 
Analyze the resume below against the job description provided.

JOB DESCRIPTION:
{job_description}

RESUME (Candidate ID: {candidate_id}):
{resume_text}

Your task:
1. Extract candidate name, skills, years of experience, education.
2. Score the candidate from 0-100 against job requirements.
3. List matched skills and missing/required skills.
4. Determine if resume has insufficient data (flag as needs_clarification).
5. Provide a 2-sentence reason for your score.

Respond ONLY in this JSON format:
{{
  "name": "...",
  "score": <number 0-100>,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3"],
  "status": "shortlisted|rejected|needs_clarification",
  "reason": "..."
}}"""

INTERVIEW_SCHEDULING_PROMPT = """You are a scheduling coordinator AI.
Given the candidate shortlist, generate preferred interview time slots.

SHORTLISTED CANDIDATES:
{candidates_json}

TODAY: {today}

For each candidate, suggest 3 interview time slots within the next 5 business days.
Respond ONLY in this JSON array format:
[
  {{
    "candidate_id": "...",
    "name": "...",
    "preferred_slots": ["YYYY-MM-DD HH:MM", "YYYY-MM-DD HH:MM", "YYYY-MM-DD HH:MM"]
  }}
]"""

CANDIDATE_EVALUATION_PROMPT = """You are a senior hiring committee AI evaluator.
Evaluate the candidate holistically using resume screening data and interview notes.

JOB DESCRIPTION:
{job_description}

RESUME SCREENING DATA:
{screening_data}

INTERVIEW NOTES:
{interview_notes}

Rubric (score each 0-10):
- Technical Skills: Does candidate meet technical requirements?
- Communication: Clear and concise in interview?
- Culture Fit: Alignment with team values?
- Experience Depth: Quality and relevance of experience?
- Leadership Potential: Shows initiative and growth mindset?

Output your final recommendation: hire / hold / reject
State your confidence (0-100%).

Respond ONLY in this JSON format:
{{
  "final_decision": "hire|hold|reject",
  "confidence": <0-100>,
  "rubric_scores": {{
    "technical_skills": <0-10>,
    "communication": <0-10>,
    "culture_fit": <0-10>,
    "experience_depth": <0-10>,
    "leadership_potential": <0-10>
  }},
  "summary": "3-sentence evaluation summary"
}}"""

CHATBOT_SYSTEM_PROMPT = """You are RecruitBot, an intelligent assistant embedded in a recruitment platform.
You have access to the candidate's resume data and can answer questions about their skills, experience, fit for roles, etc.

CANDIDATE RESUME DATA:
{resume_context}

Answer questions about this candidate naturally and helpfully. Be honest about gaps.
If asked about fit for a specific role, analyze their skills against requirements.
Keep responses concise (2-4 sentences) unless a detailed breakdown is requested."""

# ─────────────────────────────────────────────
# NODE 1: Resume Screening Agent
# ─────────────────────────────────────────────
def resume_screening_node(state: RecruitmentState) -> dict:
    llm = get_llm()
    resumes = dedupe_by_candidate_id(state["resumes"])
    screened = []
    audit = []
    clarification_needed = []

    for resume in resumes:
        cid = resume["candidate_id"]
        try:
            prompt = RESUME_SCREENING_PROMPT.format(
                job_description=state["job_description"],
                candidate_id=cid,
                resume_text=resume.get("text", ""),
            )
            response = llm.invoke([HumanMessage(content=prompt)])
            raw = response.content if hasattr(response, "content") else str(response)

            # Deterministic JSON parse
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in LLM response")

            candidate = ScreenedCandidate(
                candidate_id=cid,
                name=data.get("name", resume.get("name", "Unknown")),
                score=float(data.get("score", 0)),
                matched_skills=data.get("matched_skills", []),
                missing_skills=data.get("missing_skills", []),
                status=data.get("status", "rejected"),
                reason=data.get("reason", ""),
                resume_text=resume.get("text", ""),
            )
            screened.append(candidate)

            if candidate["status"] == "needs_clarification":
                clarification_needed.append(cid)

            audit.append(make_audit(
                "resume_screening", "screened",
                f"Score: {candidate['score']} | Status: {candidate['status']}",
                cid
            ))

        except Exception as e:
            # Fallback: deterministic scoring on error
            audit.append(make_audit("resume_screening", "error", str(e), cid))
            screened.append(ScreenedCandidate(
                candidate_id=cid,
                name=resume.get("name", "Unknown"),
                score=0.0,
                matched_skills=[],
                missing_skills=[],
                status="needs_clarification",
                reason=f"Parse error: {str(e)[:100]}",
                resume_text=resume.get("text", ""),
            ))
            clarification_needed.append(cid)

    return {
        "screened_candidates": screened,
        "clarification_needed": clarification_needed,
        "audit_log": audit,
    }

# ─────────────────────────────────────────────
# ROUTER 1: Screening Decision
# ─────────────────────────────────────────────
def screening_router(state: RecruitmentState) -> str:
    shortlisted = [c for c in state["screened_candidates"] if c["status"] == "shortlisted"]
    if not shortlisted:
        return "request_clarification"
    return "interview_scheduling"

def request_clarification_node(state: RecruitmentState) -> dict:
    """Handles resumes flagged as needing clarification."""
    audit = []
    for cid in state.get("clarification_needed", []):
        audit.append(make_audit(
            "clarification", "requested",
            "Clarification email stub sent to candidate.",
            cid
        ))
    # In production: trigger email workflow here
    return {"audit_log": audit}

# ─────────────────────────────────────────────
# NODE 2: Interview Scheduling Agent
# ─────────────────────────────────────────────
def interview_scheduling_node(state: RecruitmentState) -> dict:
    llm = get_llm()
    shortlisted = [c for c in state["screened_candidates"] if c["status"] == "shortlisted"]
    audit = []
    slots_confirmed = []
    retries = state.get("scheduling_retries", {})

    if not shortlisted:
        return {"interview_slots": [], "audit_log": audit}

    try:
        candidates_json = json.dumps([{
            "candidate_id": c["candidate_id"],
            "name": c["name"],
            "score": c["score"]
        } for c in shortlisted], indent=2)

        prompt = INTERVIEW_SCHEDULING_PROMPT.format(
            candidates_json=candidates_json,
            today=datetime.utcnow().strftime("%Y-%m-%d"),
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content if hasattr(response, "content") else str(response)

        json_match = re.search(r'\[.*\]', raw, re.DOTALL)
        scheduling_requests = json.loads(json_match.group()) if json_match else []

    except Exception as e:
        audit.append(make_audit("interview_scheduling", "llm_error", str(e)))
        # Deterministic fallback: generate slots
        scheduling_requests = []
        base = datetime.utcnow()
        for c in shortlisted:
            slots = [(base + timedelta(days=i+1)).strftime("%Y-%m-%d 10:00") for i in range(3)]
            scheduling_requests.append({
                "candidate_id": c["candidate_id"],
                "name": c["name"],
                "preferred_slots": slots
            })

    for req in scheduling_requests:
        cid = req["candidate_id"]
        retry_count = retries.get(cid, 0)

        # TOOL: Check calendar availability (deterministic stub)
        avail = calendar_api_check_availability(cid, req.get("preferred_slots", []))

        if avail["conflict"] and retry_count < 2:
            retries[cid] = retry_count + 1
            audit.append(make_audit("interview_scheduling", "conflict_retry",
                                    f"Retry {retry_count+1}/2", cid))
            # Generate new slots deterministically
            base = datetime.utcnow()
            new_slots = [(base + timedelta(days=i+3)).strftime("%Y-%m-%d 14:00") for i in range(3)]
            avail = calendar_api_check_availability(cid, new_slots)

        if avail["available_slots"]:
            chosen_slot = avail["available_slots"][0]
            booking = calendar_api_book_slot(cid, chosen_slot)
            slots_confirmed.append(InterviewSlot(
                candidate_id=cid,
                name=req["name"],
                confirmed_time=chosen_slot,
                interviewer=booking["interviewer"],
                meeting_link=booking["meeting_link"],
            ))
            audit.append(make_audit("interview_scheduling", "booked",
                                    f"Slot: {chosen_slot} | Interviewer: {booking['interviewer']}", cid))
        else:
            audit.append(make_audit("interview_scheduling", "failed",
                                    "All retries exhausted. Manual scheduling required.", cid))

    return {
        "interview_slots": slots_confirmed,
        "scheduling_retries": retries,
        "audit_log": audit,
    }

# ─────────────────────────────────────────────
# NODE 3: Candidate Evaluation Agent
# ─────────────────────────────────────────────
def candidate_evaluation_node(state: RecruitmentState) -> dict:
    llm = get_llm()
    evaluations = []
    audit = []

    # Build lookup maps
    screened_map = {c["candidate_id"]: c for c in state.get("screened_candidates", [])}
    notes_map = {n["candidate_id"]: n for n in state.get("interview_notes", [])}
    booked_ids = {s["candidate_id"] for s in state.get("interview_slots", [])}

    for cid, candidate in screened_map.items():
        if candidate["status"] != "shortlisted":
            continue
        if cid not in booked_ids:
            continue

        notes = notes_map.get(cid, {}).get("notes", "No interview notes available.")

        try:
            prompt = CANDIDATE_EVALUATION_PROMPT.format(
                job_description=state["job_description"],
                screening_data=json.dumps({
                    "score": candidate["score"],
                    "matched_skills": candidate["matched_skills"],
                    "missing_skills": candidate["missing_skills"],
                    "reason": candidate["reason"],
                }, indent=2),
                interview_notes=notes,
            )
            response = llm.invoke([HumanMessage(content=prompt)])
            raw = response.content if hasattr(response, "content") else str(response)

            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            data = json.loads(json_match.group()) if json_match else {}

            decision = data.get("final_decision", extract_decision(raw))
            confidence = float(data.get("confidence", 70)) / 100.0
            rubric = data.get("rubric_scores", {
                "technical_skills": 5, "communication": 5,
                "culture_fit": 5, "experience_depth": 5, "leadership_potential": 5
            })

            needs_review = confidence < 0.6 or decision == "hold"

            evaluations.append(Evaluation(
                candidate_id=cid,
                name=candidate["name"],
                final_decision=decision,
                confidence=confidence,
                rubric_scores=rubric,
                summary=data.get("summary", "Evaluation complete."),
                needs_human_review=needs_review,
            ))
            audit.append(make_audit("candidate_evaluation", "evaluated",
                                    f"Decision: {decision} | Confidence: {confidence:.0%}", cid))

        except Exception as e:
            audit.append(make_audit("candidate_evaluation", "error", str(e), cid))
            evaluations.append(Evaluation(
                candidate_id=cid,
                name=candidate["name"],
                final_decision="hold",
                confidence=0.5,
                rubric_scores={},
                summary=f"Evaluation error: {str(e)[:100]}",
                needs_human_review=True,
            ))

    return {"evaluations": evaluations, "audit_log": audit}

# ─────────────────────────────────────────────
# ROUTER 2: Evaluation Decision
# ─────────────────────────────────────────────
def evaluation_router(state: RecruitmentState) -> str:
    low_confidence = [e for e in state.get("evaluations", []) if e["needs_human_review"]]
    if low_confidence:
        return "human_review"
    return END

def human_review_node(state: RecruitmentState) -> dict:
    """Flags low-confidence evaluations for human review queue."""
    audit = []
    for e in state.get("evaluations", []):
        if e["needs_human_review"]:
            audit.append(make_audit("human_review", "queued",
                                    f"Decision: {e['final_decision']} | Confidence: {e['confidence']:.0%}",
                                    e["candidate_id"]))
    return {"audit_log": audit}

# ─────────────────────────────────────────────
# BUILD LangGraph
# ─────────────────────────────────────────────
def build_recruitment_graph():
    graph = StateGraph(RecruitmentState)

    # Add nodes
    graph.add_node("resume_screening", resume_screening_node)
    graph.add_node("request_clarification", request_clarification_node)
    graph.add_node("interview_scheduling", interview_scheduling_node)
    graph.add_node("candidate_evaluation", candidate_evaluation_node)
    graph.add_node("human_review", human_review_node)

    # Entry point
    graph.set_entry_point("resume_screening")

    # Router 1: after screening
    graph.add_conditional_edges(
        "resume_screening",
        screening_router,
        {
            "request_clarification": "request_clarification",
            "interview_scheduling": "interview_scheduling",
        }
    )
    graph.add_edge("request_clarification", "interview_scheduling")

    # Linear flow
    graph.add_edge("interview_scheduling", "candidate_evaluation")

    # Router 2: after evaluation
    graph.add_conditional_edges(
        "candidate_evaluation",
        evaluation_router,
        {
            "human_review": "human_review",
            END: END,
        }
    )
    graph.add_edge("human_review", END)

    return graph.compile()

# Global compiled graph
recruitment_graph = build_recruitment_graph()

# ─────────────────────────────────────────────
# Resume Chat Context Store
# ─────────────────────────────────────────────
resume_contexts: dict = {}   # candidate_id -> resume_text

# ─────────────────────────────────────────────
# Flask App
# ─────────────────────────────────────────────
app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/run", methods=["POST"])
def run_pipeline():
    """Run the full recruitment pipeline."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    job_id = data.get("job_id", f"job_{uuid.uuid4().hex[:8]}")
    job_description = data.get("job_description", "")
    raw_resumes = data.get("resumes", [])

    if not job_description or not raw_resumes:
        return jsonify({"error": "job_description and resumes[] required"}), 400

    # Store resume texts for chatbot
    for r in raw_resumes:
        cid = r.get("candidate_id") or hashlib.md5(r.get("text","").encode()).hexdigest()[:12]
        r["candidate_id"] = cid
        resume_contexts[cid] = {
            "text": r.get("text", ""),
            "name": r.get("name", "Unknown"),
        }

    initial_state = RecruitmentState(
        job_id=job_id,
        job_description=job_description,
        resumes=raw_resumes,
        screened_candidates=[],
        scheduling_requests=[],
        interview_slots=[],
        interview_notes=data.get("interview_notes", []),
        evaluations=[],
        audit_log=[],
        clarification_needed=[],
        scheduling_retries={},
        error=None,
    )

    try:
        result = recruitment_graph.invoke(initial_state)
        return jsonify({
            "job_id": result["job_id"],
            "screened_candidates": result["screened_candidates"],
            "interview_slots": result["interview_slots"],
            "evaluations": result["evaluations"],
            "audit_log": result["audit_log"],
            "clarification_needed": result["clarification_needed"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
def resume_chat():
    """Chatbot: interact with a candidate's resume."""
    data = request.get_json()
    candidate_id = data.get("candidate_id")
    message = data.get("message", "")
    history = data.get("history", [])  # [{role, content}]

    if not candidate_id or not message:
        return jsonify({"error": "candidate_id and message required"}), 400

    ctx = resume_contexts.get(candidate_id)
    if not ctx:
        return jsonify({"error": "Candidate not found. Run pipeline first."}), 404

    resume_context = f"Candidate Name: {ctx['name']}\n\nResume:\n{ctx['text']}"

    try:
        llm = get_llm()
        system = CHATBOT_SYSTEM_PROMPT.format(resume_context=resume_context)

        messages = [SystemMessage(content=system)]
        for h in history[-6:]:  # keep last 6 turns for context
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            else:
                from langchain_core.messages import AIMessage
                messages.append(AIMessage(content=h["content"]))
        messages.append(HumanMessage(content=message))

        response = llm.invoke(messages)
        reply = response.content if hasattr(response, "content") else str(response)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/candidates", methods=["GET"])
def list_candidates():
    """List all candidates loaded in memory."""
    return jsonify({
        "candidates": [
            {"candidate_id": cid, "name": v["name"]}
            for cid, v in resume_contexts.items()
        ]
    })

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "llm": "groq/llama-3.1-8b-instant" if GROQ_API_KEY else "ollama/mistral (fallback)",
        "candidates_loaded": len(resume_contexts),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })

# ─────────────────────────────────────────────
# Sample Invocation (CLI test)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Recruiter.AI Backend starting on http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
