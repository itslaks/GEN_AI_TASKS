"""
Multi-Agent Research Pipeline - Flask Backend
Implements LangGraph orchestration with Groq API, ChromaDB.
"""

import os
import re
import json
import time
import uuid
import logging
import threading
from datetime import datetime
from collections import defaultdict
from typing import TypedDict, List, Dict, Any, Optional
from functools import wraps

# ── Load .env BEFORE anything else ──────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import chromadb
from chromadb.config import Settings
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

# ============================================================================
# Configuration
# ============================================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", os.urandom(24).hex())
DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

if not GROQ_API_KEY:
    logging.warning("⚠  GROQ_API_KEY not set – the app will run in fallback mode.")

# ============================================================================
# Logging
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("research-pipeline")

# ============================================================================
# Input validation
# ============================================================================
INPUT_SCHEMA = {
    "query": {
        "type": str,
        "required": True,
        "min_length": 3,
        "max_length": 500,
        # Allow most printable chars except angle brackets (XSS) and backticks
        "pattern": r"^[^\<\>\`]{3,500}$",
    },
    "audience": {
        "type": str,
        "required": False,
        "allowed_values": ["general", "technical", "academic", "business", "student"],
    },
    "length": {
        "type": str,
        "required": False,
        "allowed_values": ["short", "medium", "long"],
    },
}


def validate_input(data: dict, schema: dict) -> tuple:
    """Validate user input against schema.  Returns (ok, error_msg)."""
    for field, rules in schema.items():
        val = data.get(field)
        if rules.get("required") and not val:
            return False, f"Field '{field}' is required."
        if val is None:
            continue
        if not isinstance(val, rules["type"]):
            return False, f"Field '{field}' has wrong type."
        if "min_length" in rules and len(val) < rules["min_length"]:
            return False, f"Field '{field}' is too short (min {rules['min_length']})."
        if "max_length" in rules and len(val) > rules["max_length"]:
            return False, f"Field '{field}' is too long (max {rules['max_length']})."
        if "allowed_values" in rules and val not in rules["allowed_values"]:
            return False, f"Field '{field}' must be one of {rules['allowed_values']}."
        if "pattern" in rules and not re.match(rules["pattern"], val):
            return False, f"Field '{field}' contains invalid characters."
    return True, None


# ============================================================================
# Rate Limiter
# ============================================================================
class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.limit = int(os.getenv("RATE_LIMIT_IP", "15"))
        self.window = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

    def allowed(self, ip: str) -> tuple:
        now = time.time()
        cutoff = now - self.window
        recent = [t for t in self.requests[ip] if t > cutoff]
        if len(recent) >= self.limit:
            retry = int(min(recent) + self.window - now) + 1
            return False, retry
        recent.append(now)
        self.requests[ip] = recent
        return True, 0


rate_limiter = RateLimiter()


def rate_limit(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        ip = request.remote_addr or "127.0.0.1"
        ok, retry = rate_limiter.allowed(ip)
        if not ok:
            resp = jsonify({"error": "Rate limit exceeded", "message": f"Retry after {retry}s"})
            resp.status_code = 429
            resp.headers["Retry-After"] = str(retry)
            return resp
        return f(*args, **kwargs)
    return wrapped


# ============================================================================
# Flask Setup
# ============================================================================
app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app, resources={r"/api/*": {"origins": os.getenv("ALLOWED_ORIGINS", "*")}})
app.config["SECRET_KEY"] = FLASK_SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

# ============================================================================
# ChromaDB
# ============================================================================
CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
os.makedirs(CHROMA_DIR, exist_ok=True)

chroma_client = chromadb.PersistentClient(
    path=CHROMA_DIR,
    settings=Settings(anonymized_telemetry=False),
)

# ============================================================================
# LLM
# ============================================================================
def get_llm():
    if GROQ_API_KEY:
        try:
            return ChatGroq(
                groq_api_key=GROQ_API_KEY,
                model_name="llama-3.1-8b-instant",
                temperature=0.7,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error(f"LLM init failed: {e}")
    return None


llm = get_llm()

# ============================================================================
# State
# ============================================================================
class AgentState(TypedDict):
    query: str
    audience: str
    length: str
    research_notes: List[Dict[str, Any]]
    citations: List[str]
    draft_report: str
    final_report: str
    logs: List[Dict[str, Any]]
    run_id: str
    collection_name: str


# In-memory run store  { run_id: { status, progress, state, ... } }
active_runs: Dict[str, dict] = {}
MAX_RUNS = 200


def add_log(state: AgentState, node: str, message: str, **kw):
    entry = {"timestamp": datetime.utcnow().isoformat(), "node": node, "message": message, **kw}
    state["logs"].append(entry)
    logger.info(f"[{node}] {message}")
    # Update progress in active_runs
    rid = state.get("run_id")
    if rid and rid in active_runs:
        active_runs[rid]["current_agent"] = node
        active_runs[rid]["logs"] = list(state["logs"])


# ============================================================================
# Agent Nodes
# ============================================================================

def researcher_node(state: AgentState) -> AgentState:
    """Researcher Agent – gathers research points via LLM, stores in ChromaDB."""
    t0 = time.time()
    add_log(state, "researcher", "🔍 Starting research phase…")

    query = state["query"]
    col_name = state["collection_name"]

    try:
        collection = chroma_client.get_or_create_collection(
            name=col_name, metadata={"description": "Research data"}
        )
    except Exception as e:
        add_log(state, "researcher", f"ChromaDB error: {e}", level="error")
        state["research_notes"] = []
        state["citations"] = []
        return state

    notes: list = []
    citations: list = []

    if llm:
        try:
            prompt = (
                f'You are a research assistant. For the topic: "{query}"\n\n'
                "Provide 5 key research points with realistic public sources.\n"
                "Format EXACTLY like this (one per block):\n"
                "POINT: <concise factual statement>\n"
                "SOURCE: <realistic URL>\n\n"
                "Keep it factual, concise, and well-sourced."
            )
            resp = llm.invoke([HumanMessage(content=prompt)])
            text = resp.content

            lines = text.strip().split("\n")
            cur_point = cur_src = ""
            for line in lines:
                line = line.strip()
                if line.upper().startswith("POINT:"):
                    cur_point = line.split(":", 1)[1].strip()
                elif line.upper().startswith("SOURCE:"):
                    cur_src = line.split(":", 1)[1].strip()
                    if cur_point and cur_src:
                        notes.append({"content": cur_point, "source": cur_src})
                        citations.append(cur_src)
                        cur_point = cur_src = ""

            if notes:
                collection.add(
                    documents=[n["content"] for n in notes],
                    metadatas=[{"source": n["source"]} for n in notes],
                    ids=[f"doc_{i}_{state['run_id']}" for i in range(len(notes))],
                )
            add_log(state, "researcher",
                     f"✅ Collected {len(notes)} research points ({int((time.time()-t0)*1000)}ms)")
        except Exception as e:
            add_log(state, "researcher", f"LLM error: {e}", level="error")
            notes = [{"content": "Fallback: configure GROQ_API_KEY for full research.", "source": "system"}]
    else:
        notes = [{"content": f"Fallback research for: {query}. Set GROQ_API_KEY.", "source": "system"}]
        add_log(state, "researcher", "⚠ Running in fallback mode (no LLM)")

    state["research_notes"] = notes
    state["citations"] = list(set(citations))
    return state


def writer_node(state: AgentState) -> AgentState:
    """Writer Agent – drafts a report from ChromaDB-retrieved chunks."""
    t0 = time.time()
    add_log(state, "writer", "✍️ Drafting report…")

    query = state["query"]
    audience = state.get("audience", "general")
    length = state.get("length", "medium")
    col_name = state["collection_name"]

    retrieved_docs = []
    retrieved_meta = []
    try:
        collection = chroma_client.get_collection(name=col_name)
        count = collection.count()
        if count > 0:
            results = collection.query(query_texts=[query], n_results=min(5, count))
            retrieved_docs = results.get("documents", [[]])[0]
            retrieved_meta = results.get("metadatas", [[]])[0]
        add_log(state, "writer", f"Retrieved {len(retrieved_docs)} chunks from ChromaDB")
    except Exception as e:
        add_log(state, "writer", f"Retrieval error: {e}", level="error")

    length_map = {"short": "2-3 paragraphs", "medium": "4-5 paragraphs", "long": "6-8 paragraphs"}

    if llm and retrieved_docs:
        try:
            context = "\n".join(
                f"- {doc} (Source: {m.get('source','?')})"
                for doc, m in zip(retrieved_docs, retrieved_meta)
            )
            prompt = (
                f"You are a professional report writer.\n"
                f"Write a {length_map.get(length,'4-5 paragraphs')} report on: \"{query}\"\n"
                f"Target audience: {audience}\n\n"
                f"Research context:\n{context}\n\n"
                "Requirements:\n"
                "- Use markdown formatting (headers, bold, bullet points)\n"
                "- Include [Source: URL] citations inline\n"
                "- Make it engaging, clear, and well-structured\n"
                "- Start with a compelling title using # heading"
            )
            resp = llm.invoke([HumanMessage(content=prompt)])
            draft = resp.content
            add_log(state, "writer",
                     f"✅ Draft complete – {len(draft)} chars ({int((time.time()-t0)*1000)}ms)")
        except Exception as e:
            add_log(state, "writer", f"LLM error: {e}", level="error")
            draft = f"# Research Report: {query}\n\n*Fallback mode – set GROQ_API_KEY.*"
    else:
        draft = f"# Research Report: {query}\n\n*Fallback mode – set GROQ_API_KEY.*"
        add_log(state, "writer", "⚠ Fallback mode")

    state["draft_report"] = draft
    return state


def editor_node(state: AgentState) -> AgentState:
    """Editor Agent – polishes the draft."""
    t0 = time.time()
    add_log(state, "editor", "✨ Editing & polishing…")

    draft = state["draft_report"]
    citations = state["citations"]

    if llm and draft:
        try:
            prompt = (
                "You are an expert editor. Improve this draft report:\n\n"
                f"{draft}\n\n"
                f"Available citations: {', '.join(citations[:10])}\n\n"
                "Tasks:\n"
                "1. Improve clarity, structure, and flow\n"
                "2. Ensure citations are properly placed\n"
                "3. Fix grammar and readability\n"
                "4. Keep markdown formatting\n"
                "5. Make it publication-ready\n\n"
                "Return the improved report in markdown."
            )
            resp = llm.invoke([HumanMessage(content=prompt)])
            final = resp.content
            add_log(state, "editor",
                     f"✅ Editing complete – {len(final)} chars ({int((time.time()-t0)*1000)}ms)")
        except Exception as e:
            add_log(state, "editor", f"LLM error: {e}", level="error")
            final = draft
    else:
        final = draft
        add_log(state, "editor", "⚠ Skipped editing (fallback)")

    state["final_report"] = final
    add_log(state, "editor", "🎉 Pipeline finished!")
    return state


# ============================================================================
# LangGraph Workflow
# ============================================================================
def build_graph():
    wf = StateGraph(AgentState)
    wf.add_node("researcher", researcher_node)
    wf.add_node("writer", writer_node)
    wf.add_node("editor", editor_node)
    wf.set_entry_point("researcher")
    wf.add_edge("researcher", "writer")
    wf.add_edge("writer", "editor")
    wf.add_edge("editor", END)
    return wf.compile()


graph = build_graph()


# ============================================================================
# Routes
# ============================================================================

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "llm_available": llm is not None,
        "groq_key_set": bool(GROQ_API_KEY),
        "timestamp": datetime.utcnow().isoformat(),
    })


@app.route("/api/run", methods=["POST"])
@rate_limit
def run_pipeline():
    """Run the full 3-agent research pipeline (synchronous)."""
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    ok, err = validate_input(data, INPUT_SCHEMA)
    if not ok:
        return jsonify({"error": "Validation error", "message": err}), 400

    query = data["query"].strip()
    audience = data.get("audience", "general")
    length = data.get("length", "medium")

    run_id = str(uuid.uuid4())
    # ChromaDB collection names: 3-63 chars, [a-zA-Z0-9_-], start/end alphanumeric
    safe_id = run_id.replace("-", "")[:40]
    col_name = f"r{safe_id}"

    # Enforce max runs
    if len(active_runs) >= MAX_RUNS:
        cutoff = time.time() - 3600
        for rid in list(active_runs):
            if active_runs[rid].get("completed_at", 0) < cutoff:
                del active_runs[rid]
        if len(active_runs) >= MAX_RUNS:
            return jsonify({"error": "Server busy", "message": "Try again later."}), 503

    initial_state: AgentState = {
        "query": query,
        "audience": audience,
        "length": length,
        "research_notes": [],
        "citations": [],
        "draft_report": "",
        "final_report": "",
        "logs": [],
        "run_id": run_id,
        "collection_name": col_name,
    }

    active_runs[run_id] = {
        "status": "running",
        "started_at": time.time(),
        "current_agent": "researcher",
        "logs": [],
        "state": initial_state,
    }

    try:
        final = graph.invoke(initial_state)
        active_runs[run_id].update({
            "status": "completed",
            "completed_at": time.time(),
            "state": final,
        })
        return jsonify({
            "run_id": run_id,
            "status": "completed",
            "final_report": final.get("final_report", ""),
            "draft_report": final.get("draft_report", ""),
            "research_notes": final.get("research_notes", []),
            "citations": final.get("citations", []),
            "logs": final.get("logs", []),
        })
    except Exception as e:
        logger.exception(f"Pipeline failed for {run_id}")
        active_runs[run_id]["status"] = "failed"
        active_runs[run_id]["error"] = str(e)
        return jsonify({"error": "Pipeline failed", "message": str(e), "run_id": run_id}), 500


@app.route("/api/status/<run_id>")
@rate_limit
def get_status(run_id):
    try:
        uuid.UUID(run_id)
    except ValueError:
        return jsonify({"error": "Invalid run ID"}), 400

    run = active_runs.get(run_id)
    if not run:
        return jsonify({"error": "Run not found"}), 404

    return jsonify({
        "run_id": run_id,
        "status": run.get("status"),
        "current_agent": run.get("current_agent"),
        "logs": run.get("logs", []),
    })


@app.route("/api/history")
@rate_limit
def history():
    """Return last 20 completed runs (lightweight)."""
    completed = [
        {"run_id": rid, "query": r["state"].get("query", ""), "status": r["status"],
         "completed_at": r.get("completed_at")}
        for rid, r in active_runs.items()
        if r.get("status") == "completed"
    ]
    completed.sort(key=lambda x: x.get("completed_at", 0), reverse=True)
    return jsonify(completed[:20])


# ── Error handlers ──────────────────────────────────────────────────────────
@app.errorhandler(400)
def h400(e):
    return jsonify({"error": "Bad request", "message": str(e)}), 400

@app.errorhandler(429)
def h429(e):
    return jsonify({"error": "Rate limited", "message": "Slow down."}), 429

@app.errorhandler(500)
def h500(e):
    logger.error(f"500: {e}")
    return jsonify({"error": "Internal error"}), 500


# ============================================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    logger.info(f"🚀 Starting on http://localhost:{port}")
    logger.info(f"   LLM available : {llm is not None}")
    logger.info(f"   GROQ key set  : {bool(GROQ_API_KEY)}")
    app.run(host="0.0.0.0", port=port, debug=DEBUG_MODE)
