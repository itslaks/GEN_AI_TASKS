"""
Content Moderation Workflow with Human-in-the-Loop (HITL)
LangGraph workflow + Flask API + Groq LLM (fallback: Ollama Mistral)
"""

import os
import uuid
import json
import time
import threading
import requests
from datetime import datetime, timezone
from typing import Optional, TypedDict
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

# ─────────────────────────────────────────────
# LangGraph State Model
# ─────────────────────────────────────────────
class ModerationState(TypedDict, total=False):
    content_id: str
    text: str
    metadata: dict
    moderation_score: float
    moderation_reasons: list
    route: str                     # auto_approve | human_review | auto_deny
    review_id: Optional[str]
    human_decision: Optional[str]   # approve | deny
    human_comment: Optional[str]
    final_decision: Optional[str]
    audit_log: list
    errors: list
    llm_analysis: Optional[str]

# ─────────────────────────────────────────────
# In-memory stores
# ─────────────────────────────────────────────
review_queue: dict[str, dict] = {}    # thread_id -> state dict
completed_items: dict[str, dict] = {} # content_id -> state dict
_queue_lock = threading.Lock()

# ─────────────────────────────────────────────
# Thresholds (documented)
# ─────────────────────────────────────────────
LOW_THRESHOLD  = 0.30   # score < 0.30 → auto-approve
HIGH_THRESHOLD = 0.70   # score >= 0.70 → auto-deny
# 0.30 <= score < 0.70 → human_review

# ─────────────────────────────────────────────
# Rule-based heuristic scoring (no external API)
# ─────────────────────────────────────────────
TOXIC_PATTERNS = {
    "hate":       (["hate", "racist", "bigot", "slur"], 0.35),
    "violence":   (["kill", "murder", "attack", "bomb", "shoot", "stab"], 0.40),
    "spam":       (["buy now", "click here", "free money", "winner", "prize"], 0.20),
    "profanity":  (["damn", "hell", "crap", "stupid", "idiot"], 0.10),
    "explicit":   (["porn", "nude", "sex", "xxx"], 0.45),
    "threat":     (["i will hurt", "you will pay", "watch your back", "i know where"], 0.50),
    "self_harm":  (["suicide", "self-harm", "end my life", "want to die"], 0.45),
}

def rule_based_score(text: str) -> tuple[float, list[str]]:
    text_lower = text.lower()
    score = 0.0
    reasons = []
    for category, (keywords, weight) in TOXIC_PATTERNS.items():
        for kw in keywords:
            if kw in text_lower:
                score += weight
                reasons.append(f"{category}:{kw}(+{weight:.2f})")
                break
    # Length heuristic: very short or very long content gets slight bump
    if len(text) < 5:
        score += 0.05
        reasons.append("too_short(+0.05)")
    # Clamp to [0, 1]
    return min(score, 1.0), reasons

# ─────────────────────────────────────────────
# LLM Analysis via Groq (llama-3.1-8b-instant)
# Fallback: Ollama Mistral (local)
# ─────────────────────────────────────────────
def llm_analyze(text: str, score: float, reasons: list) -> str:
    groq_key = os.getenv("GROQ_API_KEY", "")
    prompt = (
        f"You are a content moderation assistant.\n"
        f"Content: \"{text}\"\n"
        f"Heuristic score: {score:.2f} (0=safe, 1=toxic)\n"
        f"Detected patterns: {', '.join(reasons) if reasons else 'none'}\n"
        f"In 2-3 sentences, explain what is problematic (or why it is safe) "
        f"and suggest approve or deny. Be concise."
    )

    # Try Groq first
    if groq_key:
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.3,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[LLM] Groq error: {e}, trying Ollama...")

    # Fallback: Ollama Mistral (local)
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "mistral", "prompt": prompt, "stream": False},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"[LLM] Ollama error: {e}")

    return "LLM analysis unavailable (no Groq key and Ollama not running). Rule-based scoring applied."

# ─────────────────────────────────────────────
# LangGraph Nodes
# ─────────────────────────────────────────────
def _log(state: ModerationState, node: str, summary: str) -> list:
    ts = datetime.now(timezone.utc).isoformat()
    event = {"ts": ts, "node": node, "summary": summary}
    log = state.get("audit_log", []).copy()
    log.append(event)
    print(f"[{ts}] [{node}] {summary}")
    return log


def node_ingest(state: ModerationState) -> ModerationState:
    log = _log(state, "ingest", f"Received content id={state.get('content_id')} len={len(state.get('text',''))}")
    return {"audit_log": log}


def node_auto_moderate(state: ModerationState) -> ModerationState:
    text = state.get("text", "")
    score, reasons = rule_based_score(text)
    
    if score < LOW_THRESHOLD:
        route = "auto_approve"
    elif score >= HIGH_THRESHOLD:
        route = "auto_deny"
    else:
        route = "human_review"
        
    analysis = llm_analyze(text, score, reasons)
    
    # We update state locally for _log
    state_updates: ModerationState = {
        "moderation_score": score,
        "moderation_reasons": reasons,
        "llm_analysis": analysis,
        "route": route
    }
    temp_state = state.copy()
    temp_state.update(state_updates)
    
    log = _log(temp_state, "auto_moderate",
         f"score={score:.2f} reasons={reasons} llm={'ok' if analysis else 'none'} route={route}")
         
    state_updates["audit_log"] = log
    return state_updates


def route_condition(state: ModerationState) -> str:
    # Router logic from Langgraph edges.
    route = state.get("route")
    if route == "human_review":
        return "human_review"
    return "finalize"


def node_human_review(state: ModerationState) -> ModerationState:
    """
    HITL gate: This node only executes AFTER the pause has been unblocked 
    by human input to resume the workflow.
    """
    review_id = state.get("review_id")
    decision = state.get("human_decision")
    log = _log(state, "human_review", f"Resuming review_id={review_id} with human_decision={decision}")
    return {"audit_log": log}


def node_finalize(state: ModerationState) -> ModerationState:
    decision = state.get("human_decision")
    comment = state.get("human_comment")
    route = state.get("route")
    
    if decision:
        final_decision = decision
    elif route == "auto_approve":
        final_decision = "approve"
    elif route == "auto_deny":
        final_decision = "deny"
    else:
        final_decision = decision or "pending"

    temp_state = state.copy()
    temp_state["final_decision"] = final_decision
    log = _log(temp_state, "finalize",
         f"final_decision={final_decision} human={decision}")
         
    return {
        "final_decision": final_decision,
        "audit_log": log
    }

# ─────────────────────────────────────────────
# Prepare LangGraph
# ─────────────────────────────────────────────
checkpointer = MemorySaver()
builder = StateGraph(ModerationState)

builder.add_node("ingest", node_ingest)
builder.add_node("auto_moderate", node_auto_moderate)
builder.add_node("human_review", node_human_review)
builder.add_node("finalize", node_finalize)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "auto_moderate")
builder.add_conditional_edges("auto_moderate", route_condition, {
    "finalize": "finalize",
    "human_review": "human_review"
})
builder.add_edge("human_review", "finalize")
builder.add_edge("finalize", END)

# IMPORTANT: we interrupt BEFORE human_review.
graph = builder.compile(checkpointer=checkpointer, interrupt_before=["human_review"])


# ─────────────────────────────────────────────
# Flask API Routes
# ─────────────────────────────────────────────
app = Flask(__name__, static_folder=".", static_url_path="")


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/moderate", methods=["POST"])
def moderate():
    """Submit content for moderation."""
    data = request.get_json(force=True)
    if not data or not data.get("text"):
        return jsonify({"error": "text field required"}), 400
        
    content_id = data.get("id", str(uuid.uuid4()))
    config = {"configurable": {"thread_id": content_id}}
    
    initial_state: ModerationState = {
        "content_id": content_id,
        "text": data.get("text", ""),
        "metadata": data.get("metadata", {}),
        "review_id": content_id, # for simplicity we use content_id as review_id
        "audit_log": []
    }
    
    # Run graph
    for event in graph.stream(initial_state, config):
        pass # Stream to safely execute nodes until completion or interruption
        
    state_desc = graph.get_state(config)
    state = state_desc.values
    
    # Check if workflow paused at human_review
    if state_desc.next and "human_review" in state_desc.next:
        with _queue_lock:
            review_queue[content_id] = state.copy()
            
        return jsonify({
            "status": "pending_review",
            "review_id": content_id,
            "content_id": content_id,
            "score": state.get("moderation_score"),
            "reasons": state.get("moderation_reasons"),
            "llm_analysis": state.get("llm_analysis"),
        }), 200
    else:
        with _queue_lock:
            completed_items[content_id] = state.copy()
            
        return jsonify({
            "status": "completed",
            "content_id": content_id,
            "final_decision": state.get("final_decision"),
            "score": state.get("moderation_score"),
            "reasons": state.get("moderation_reasons"),
            "llm_analysis": state.get("llm_analysis"),
            "route": state.get("route"),
            "audit_log": state.get("audit_log"),
        }), 200


@app.route("/api/queue", methods=["GET"])
def get_queue():
    """List all pending human-review items."""
    with _queue_lock:
        items = []
        for rid, state in review_queue.items():
            items.append({
                "review_id": rid,
                "content_id": state.get("content_id"),
                "text": state.get("text"),
                "score": state.get("moderation_score"),
                "reasons": state.get("moderation_reasons"),
                "llm_analysis": state.get("llm_analysis"),
                "metadata": state.get("metadata"),
                "audit_log": state.get("audit_log"),
            })
    return jsonify({"queue": items, "count": len(items)}), 200


@app.route("/api/review/<review_id>", methods=["POST"])
def submit_review(review_id):
    """Human submits approve/deny decision."""
    data = request.get_json(force=True)
    decision = data.get("decision")  # "approve" | "deny"
    comment = data.get("comment", "")

    if decision not in ("approve", "deny"):
        return jsonify({"error": "decision must be 'approve' or 'deny'"}), 400

    config = {"configurable": {"thread_id": review_id}}
    state_desc = graph.get_state(config)
    
    if not state_desc or not state_desc.next or "human_review" not in state_desc.next:
        return jsonify({"error": "review_id not found or already resolved"}), 404

    # Apply Human input
    graph.update_state(config, {"human_decision": decision, "human_comment": comment}, as_node=None)
    
    # Resume Workflow
    for event in graph.stream(None, config):
        pass
        
    final_state_desc = graph.get_state(config)
    final_state = final_state_desc.values

    # Move from queue to completed
    with _queue_lock:
        review_queue.pop(review_id, None)
        completed_items[final_state.get("content_id")] = final_state.copy()

    return jsonify({
        "status": "completed",
        "content_id": final_state.get("content_id"),
        "final_decision": final_state.get("final_decision"),
        "human_comment": final_state.get("human_comment"),
        "audit_log": final_state.get("audit_log"),
    }), 200


@app.route("/api/completed", methods=["GET"])
def get_completed():
    """List all completed moderation decisions."""
    with _queue_lock:
        items = []
        for cid, state in completed_items.items():
            items.append({
                "content_id": cid,
                "text": state.get("text"),
                "score": state.get("moderation_score"),
                "route": state.get("route"),
                "final_decision": state.get("final_decision"),
                "human_decision": state.get("human_decision"),
                "human_comment": state.get("human_comment"),
                "llm_analysis": state.get("llm_analysis"),
                "audit_log": state.get("audit_log"),
            })
    return jsonify({"completed": items, "count": len(items)}), 200


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Aggregate stats for dashboard."""
    with _queue_lock:
        pending = len(review_queue)
        total = len(completed_items)
        approved = sum(1 for s in completed_items.values() if s.get("final_decision") == "approve")
        denied   = sum(1 for s in completed_items.values() if s.get("final_decision") == "deny")
        auto_approved = sum(1 for s in completed_items.values() if s.get("route") == "auto_approve")
        auto_denied   = sum(1 for s in completed_items.values() if s.get("route") == "auto_deny")
        human_reviewed = sum(1 for s in completed_items.values() if s.get("route") == "human_review")
    return jsonify({
        "pending_review": pending,
        "total_completed": total,
        "approved": approved,
        "denied": denied,
        "auto_approved": auto_approved,
        "auto_denied": auto_denied,
        "human_reviewed": human_reviewed,
    }), 200


if __name__ == "__main__":
    print("=" * 60)
    print("  Content Moderation HITL System (LangGraph Native)")
    print(f"  Thresholds: auto-approve < {LOW_THRESHOLD} | auto-deny >= {HIGH_THRESHOLD}")
    print(f"  Groq key: {'SET' if os.getenv('GROQ_API_KEY') else 'NOT SET (rule-based only)'}")
    print("  UI: http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, port=5000)
