"""
Multi-Agent Research Pipeline — Flask Backend
==============================================
Security hardening applied per OWASP top-10:
  1. Rate limiting  (flask-limiter, IP + Key)
  2. Strict input validation (Pydantic schema)
  3. Secrets only from environment variables
"""

import os, uuid, time, json, logging, re, hashlib
from datetime import datetime, timezone
from functools import lru_cache
from typing import TypedDict, List, Optional, Any
from pathlib import Path

# ─── Load .env early so all os.getenv calls see the values ────────────────────
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pydantic import BaseModel, Field, field_validator, model_validator

# ─── LangGraph / LangChain imports ────────────────────────────────────────────
from langgraph.graph import StateGraph, END

# ─── ChromaDB ─────────────────────────────────────────────────────────────────
import chromadb
from chromadb.config import Settings

# ─── HTTP scraping (Researcher agent) ─────────────────────────────────────────
import requests as http_req
from bs4 import BeautifulSoup

# ──────────────────────────────────────────────────────────────────────────────
# SECURITY: Logging — never emit API keys or secrets in log lines.
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("research_pipeline")

# ──────────────────────────────────────────────────────────────────────────────
# SECURITY: Secrets are read exclusively from environment variables.
#           Hard-coded fallback values are ONLY non-sensitive defaults.
# ──────────────────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
FLASK_SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "change-me-before-production")
CHROMA_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
FORCE_FALLBACK: bool = os.getenv("FORCE_FALLBACK", "0") == "1"

GROQ_MODEL = "llama-3.1-8b-instant"

# Warn loudly if the secret key was never changed.
if FLASK_SECRET_KEY == "change-me-before-production":
    logger.warning(
        "FLASK_SECRET_KEY is using the insecure default value. "
        "Set a strong random value in your .env file before deploying."
    )

# ──────────────────────────────────────────────────────────────────────────────
# Flask app — static_folder points to the same directory so index.html is served
# ──────────────────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = FLASK_SECRET_KEY
CORS(app, resources={r"/api/*": {"origins": "*"}})   # Tighten origins in prod

# ──────────────────────────────────────────────────────────────────────────────
# SECURITY: Rate limiting using flask-limiter.
#   - Default: IP-based.
#   - POST /api/run  → 10 requests / min  (heavy LLM call).
#   - GET  /api/status → 60 requests / min  (lightweight poll).
#   - 429 response includes Retry-After header (standards-compliant).
# ──────────────────────────────────────────────────────────────────────────────
RATE_LIMIT_RUN: str    = os.getenv("RATE_LIMIT_RUN",    "10 per minute")
RATE_LIMIT_STATUS: str = os.getenv("RATE_LIMIT_STATUS", "60 per minute")

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    headers_enabled=True,           # Adds RateLimit-* and Retry-After headers
    storage_uri="memory://",        # Use Redis URI in production
)

# ──────────────────────────────────────────────────────────────────────────────
# SECURITY: Input validation schema using Pydantic v2.
#   - Maximum 397 characters on every user-supplied string.
#   - Only the three expected fields are allowed; extra fields are rejected.
#   - Type coercion to str + regex sanitation prevents injection.
# ──────────────────────────────────────────────────────────────────────────────
MAX_FIELD_LEN = 397  # OWASP: explicit length limits
_SAFE_PATTERN = re.compile(r"[^\w\s.,\-?!:;'\"()\[\]@#%&+=/<>]", re.UNICODE)

class RunRequest(BaseModel):
    """Strict schema — no extra fields allowed."""

    model_config = {"extra": "forbid"}   # Reject unexpected keys

    query: str = Field(..., min_length=3, max_length=MAX_FIELD_LEN)
    audience: Optional[str] = Field(default="general public", max_length=MAX_FIELD_LEN)
    length: Optional[str] = Field(default="medium", max_length=MAX_FIELD_LEN)

    @field_validator("query", "audience", "length", mode="before")
    @classmethod
    def sanitize_string(cls, v: Any) -> str:
        """Strip leading/trailing whitespace and remove dangerous characters."""
        if v is None:
            return v
        if not isinstance(v, str):
            v = str(v)
        # Remove chars outside the safe allowlist
        v = _SAFE_PATTERN.sub("", v).strip()
        return v

    @field_validator("length")
    @classmethod
    def validate_length_choice(cls, v: Optional[str]) -> Optional[str]:
        """Restrict 'length' to known values to prevent prompt injection."""
        allowed = {"short", "medium", "long", None, ""}
        if v not in allowed:
            raise ValueError(f"'length' must be one of {sorted(a for a in allowed if a)}.")
        return v or "medium"


# ──────────────────────────────────────────────────────────────────────────────
# In-memory run store  (replace with Redis/DB in production)
# ──────────────────────────────────────────────────────────────────────────────
_run_store: dict[str, dict] = {}


# ──────────────────────────────────────────────────────────────────────────────
# ChromaDB helper
# ──────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_chroma_client():
    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DIR)


def get_or_create_collection(run_id: str):
    client = get_chroma_client()
    col_name = f"research_{run_id[:16]}"   # ChromaDB name length limit
    return client.get_or_create_collection(
        name=col_name,
        metadata={"hnsw:space": "cosine"},
    )


# ──────────────────────────────────────────────────────────────────────────────
# LLM helpers — Groq (primary) / stub fallback (no paid service required)
# ──────────────────────────────────────────────────────────────────────────────
def _groq_available() -> bool:
    """Return True only when a non-empty key is configured and fallback not forced."""
    return bool(GROQ_API_KEY) and not FORCE_FALLBACK


def call_llm(prompt: str, system: str = "You are a helpful research assistant.") -> tuple[str, float, int]:
    """
    Call the LLM and return (response_text, latency_seconds, est_tokens).

    Falls back gracefully to a local stub when Groq is unavailable,
    so the demo runs end-to-end without paid credentials.
    """
    start = time.time()

    if _groq_available():
        try:
            from groq import Groq
            # SECURITY: API key loaded from env var — never embedded in source.
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=1024,
                temperature=0.7,
            )
            text = response.choices[0].message.content or ""
            tokens = response.usage.total_tokens if response.usage else len(text.split())
            return text, time.time() - start, tokens
        except Exception as exc:
            logger.warning("Groq call failed (%s). Activating fallback stub.", exc)

    # ── Local fallback stub ───────────────────────────────────────────────────
    text = _fallback_stub(prompt, system)
    return text, time.time() - start, len(text.split())


def _fallback_stub(prompt: str, system: str) -> str:
    """
    Minimal deterministic stub that produces plausible structure.
    This runs entirely locally with no external calls — safe for offline demos.
    """
    query_hint = prompt[:120].replace("\n", " ")

    if "researcher" in system.lower() or "research" in system.lower():
        return (
            f"[FALLBACK MODE — Groq unavailable]\n\n"
            f"**Research Notes on:** {query_hint}\n\n"
            "Key findings:\n"
            "1. This topic has been studied extensively in recent literature.\n"
            "2. Multiple peer-reviewed sources confirm the core claims.\n"
            "3. Emerging research suggests further investigation is warranted.\n\n"
            "Sources consulted:\n"
            "- https://en.wikipedia.org/wiki/Main_Page\n"
            "- https://arxiv.org/\n"
        )
    if "writer" in system.lower():
        return (
            f"[FALLBACK MODE — Groq unavailable]\n\n"
            f"# Research Report\n\n"
            f"## Introduction\nThis report examines: {query_hint}\n\n"
            "## Key Findings\nBased on the research notes, several important points emerge.\n\n"
            "## Conclusion\nFurther study is recommended to validate these findings.\n\n"
            "**Citations:**\n- https://en.wikipedia.org/wiki/Main_Page\n"
        )
    # editor
    return (
        f"[FALLBACK MODE — Groq unavailable]\n\n"
        "The draft report has been reviewed. Structure and clarity are adequate. "
        "All citations map to their stated claims. No uncertain statements detected in fallback mode."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Web scraping helper (Researcher agent)
# ──────────────────────────────────────────────────────────────────────────────
_FETCH_TIMEOUT = 8   # seconds
_MAX_CONTENT_CHARS = 4000


def safe_fetch(url: str) -> str:
    """Fetch and clean text from a public URL. Returns empty string on failure."""
    try:
        resp = http_req.get(
            url,
            timeout=_FETCH_TIMEOUT,
            headers={"User-Agent": "ResearchBot/1.0 (+https://github.com/example)"},
            allow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Strip nav, script, style blobs
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:_MAX_CONTENT_CHARS]
    except Exception as exc:
        logger.debug("Failed to fetch %s: %s", url, exc)
        return ""


# ──────────────────────────────────────────────────────────────────────────────
# LangGraph state definition
# ──────────────────────────────────────────────────────────────────────────────
class PipelineState(TypedDict):
    run_id:       str
    query:        str
    audience:     str
    length:       str
    logs:         List[dict]
    sources:      List[str]     # URLs collected by Researcher
    chunks:       List[str]     # text chunks stored in ChromaDB
    notes:        str           # Researcher's synthesis
    draft:        str           # Writer's draft
    final_report: str           # Editor's final report
    citations:    List[str]     # de-duplicated citation list


def _log_entry(state: PipelineState, node: str, message: str,
               latency: float = 0.0, tokens: int = 0) -> dict:
    entry = {
        "ts":      datetime.now(timezone.utc).isoformat(),
        "node":    node,
        "message": message,
        "latency_s": round(latency, 3),
        "tokens":  tokens,
    }
    state["logs"].append(entry)
    logger.info("[%s] %s (%.2fs, %d tok)", node, message, latency, tokens)
    # Mirror to run store so /api/status can stream progress
    if state["run_id"] in _run_store:
        _run_store[state["run_id"]]["logs"] = list(state["logs"])
    return entry


# ──────────────────────────────────────────────────────────────────────────────
# Agent nodes
# ──────────────────────────────────────────────────────────────────────────────
_SEARCH_URLS = [
    "https://en.wikipedia.org/wiki/{q}",
    "https://simple.wikipedia.org/wiki/{q}",
]

def researcher_node(state: PipelineState) -> PipelineState:
    """
    Agent 1 — Researcher
    Fetches public web pages, chunks the content, embeds & stores in ChromaDB,
    then synthesises research notes via LLM.
    """
    _log_entry(state, "researcher", "Starting research phase")
    q_slug = state["query"].replace(" ", "_")[:60]

    urls = [u.format(q=q_slug) for u in _SEARCH_URLS]
    raw_chunks: List[str] = []
    found_urls: List[str] = []

    for url in urls:
        text = safe_fetch(url)
        if text:
            found_urls.append(url)
            # Split into ~500-char chunks
            for i in range(0, len(text), 500):
                raw_chunks.append(text[i:i+500])
            _log_entry(state, "researcher", f"Fetched {url}")

    # ── Store chunks in ChromaDB ──────────────────────────────────────────────
    if raw_chunks:
        col = get_or_create_collection(state["run_id"])
        ids  = [hashlib.md5(c.encode()).hexdigest()[:16] for c in raw_chunks]
        docs = raw_chunks
        col.upsert(documents=docs, ids=ids)
        _log_entry(state, "researcher",
                   f"Stored {len(raw_chunks)} chunks in ChromaDB (retrieval_hits={len(raw_chunks)})")

        # Retrieve top-5 relevant chunks via similarity search
        results = col.query(query_texts=[state["query"]], n_results=min(5, len(raw_chunks)))
        retrieved = results["documents"][0] if results["documents"] else raw_chunks[:5]
    else:
        retrieved = []

    context = "\n---\n".join(retrieved) if retrieved else "(no web content retrieved)"

    prompt = (
        f"You are a researcher. The user wants a report on: '{state['query']}'\n"
        f"Target audience: {state['audience']}\n\n"
        f"Retrieved web excerpts:\n{context}\n\n"
        "Write concise research notes with key facts, statistics, and a list of "
        "source URLs. Do NOT fabricate URLs — only use the ones provided."
    )
    notes, latency, tokens = call_llm(
        prompt,
        system="You are an accurate, rigorous research assistant who never fabricates facts."
    )
    _log_entry(state, "researcher", "Research notes complete", latency, tokens)

    state["sources"]  = found_urls
    state["chunks"]   = raw_chunks[:20]   # persist first 20 for citations
    state["notes"]    = notes
    state["citations"] = found_urls
    return state


def writer_node(state: PipelineState) -> PipelineState:
    """
    Agent 2 — Writer
    Drafts a structured report from the researcher's notes.
    """
    _log_entry(state, "writer", "Starting drafting phase")

    length_guide = {"short": "~300 words", "medium": "~600 words", "long": "~1000 words"}
    target_len = length_guide.get(state["length"], "~600 words")

    prompt = (
        f"You are a professional technical writer.\n"
        f"Write a {target_len} report on '{state['query']}' "
        f"for the audience: '{state['audience']}'.\n\n"
        f"Use the following research notes as your ONLY source of facts:\n"
        f"{state['notes']}\n\n"
        "Structure: Executive Summary, Key Findings (3-5 bullet points), "
        "Detailed Analysis, Conclusion. "
        "Append a '## Citations' section listing only URLs from the notes. "
        "Do NOT invent facts or URLs."
    )
    draft, latency, tokens = call_llm(
        prompt,
        system="You are a clear, structured technical writer who sticks strictly to sourced facts."
    )
    _log_entry(state, "writer", "Draft report complete", latency, tokens)
    state["draft"] = draft
    return state


def editor_node(state: PipelineState) -> PipelineState:
    """
    Agent 3 — Editor
    Reviews the draft for clarity, structure, and citation integrity.
    Adds ⚠️ flags for uncertain claims.
    """
    _log_entry(state, "editor", "Starting editing phase")

    prompt = (
        "You are an expert editor. Review and improve the following draft report.\n\n"
        f"Draft:\n{state['draft']}\n\n"
        f"Research notes (ground truth):\n{state['notes']}\n\n"
        "Tasks:\n"
        "1. Improve clarity, sentence flow, and paragraph structure.\n"
        "2. Verify each factual claim maps to the research notes; "
        "   flag uncertain statements with ⚠️ UNCERTAIN and explain why.\n"
        "3. Ensure the Citations section lists ONLY URLs present in the research notes.\n"
        "4. Return the full, polished report — do not truncate."
    )
    final, latency, tokens = call_llm(
        prompt,
        system="You are a meticulous editor who prioritises accuracy over fluency."
    )
    _log_entry(state, "editor", "Editing complete", latency, tokens)

    # Extract unique citations from the finished report
    url_pattern = re.compile(r"https?://[^\s)\]\"'>]+")
    found_urls  = url_pattern.findall(final)
    unique_cits = list(dict.fromkeys(found_urls))   # preserve order, deduplicate

    state["final_report"] = final
    state["citations"]    = unique_cits or state["citations"]
    _log_entry(state, "editor",
               f"Extracted {len(unique_cits)} unique citations from report")
    return state


# ──────────────────────────────────────────────────────────────────────────────
# Build LangGraph pipeline
# ──────────────────────────────────────────────────────────────────────────────
def build_graph():
    g = StateGraph(PipelineState)
    g.add_node("researcher", researcher_node)
    g.add_node("writer",     writer_node)
    g.add_node("editor",     editor_node)
    g.set_entry_point("researcher")
    g.add_edge("researcher", "writer")
    g.add_edge("writer",     "editor")
    g.add_edge("editor",     END)
    return g.compile()


_pipeline = build_graph()


# ──────────────────────────────────────────────────────────────────────────────
# Flask routes
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    """Serve the single-page frontend."""
    return send_from_directory(".", "index.html")


# ── SECURITY: request content-type guard ──────────────────────────────────────
@app.before_request
def require_json_for_api():
    """
    For all /api/ POST requests, enforce Content-Type: application/json.
    This mitigates CSRF-style attacks that rely on non-JSON form submissions.
    """
    if request.path.startswith("/api/") and request.method == "POST":
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 415


@app.errorhandler(429)
def ratelimit_handler(e):
    """
    SECURITY: Standards-compliant 429 Too Many Requests with Retry-After.
    flask-limiter adds Retry-After automatically when headers_enabled=True.
    """
    return jsonify({
        "error": "Rate limit exceeded. Please slow down.",
        "retry_after": e.description,
    }), 429


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/run
# SECURITY: Rate limited (10/min), input validated via Pydantic, no raw SQL/shell.
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/run", methods=["POST"])
@limiter.limit(RATE_LIMIT_RUN)
def run_pipeline():
    """
    Launch the 3-agent research pipeline.
    Accepts: { query, audience?, length? }
    Returns: { run_id, final_report, citations, logs }
    """
    raw_body = request.get_json(silent=True)
    if raw_body is None:
        return jsonify({"error": "Invalid or missing JSON body."}), 400

    # ── Validate & sanitise input ─────────────────────────────────────────────
    try:
        validated = RunRequest.model_validate(raw_body)
    except Exception as exc:
        # Return structured validation errors (safe — no internal tracebacks)
        errors = json.loads(exc.json()) if hasattr(exc, "json") else [{"msg": str(exc)}]
        return jsonify({"error": "Input validation failed.", "details": errors}), 422

    run_id = str(uuid.uuid4())
    _run_store[run_id] = {"status": "running", "logs": [], "progress": 0}

    initial_state: PipelineState = {
        "run_id":       run_id,
        "query":        validated.query,
        "audience":     validated.audience,
        "length":       validated.length,
        "logs":         [],
        "sources":      [],
        "chunks":       [],
        "notes":        "",
        "draft":        "",
        "final_report": "",
        "citations":    [],
    }

    try:
        result = _pipeline.invoke(initial_state)
    except Exception as exc:
        logger.exception("Pipeline error for run_id=%s", run_id)
        _run_store[run_id]["status"] = "error"
        # SECURITY: generic error — never leak internal exception details to client
        return jsonify({"error": "Pipeline execution failed. Check server logs."}), 500

    _run_store[run_id]["status"]   = "done"
    _run_store[run_id]["progress"] = 100

    response_payload = {
        "run_id":       run_id,
        "final_report": result.get("final_report", ""),
        "citations":    result.get("citations",    []),
        "logs":         result.get("logs",         []),
    }
    return jsonify(response_payload), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/status/<run_id>
# SECURITY: Rate limited (60/min), run_id validated as UUID to prevent path traversal.
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/status/<run_id>", methods=["GET"])
@limiter.limit(RATE_LIMIT_STATUS)
def get_status(run_id: str):
    """Return progress + logs for a running or completed pipeline run."""

    # SECURITY: Validate run_id is a strict UUID v4 — prevents path/injection attacks.
    try:
        uuid.UUID(run_id, version=4)
    except ValueError:
        return jsonify({"error": "Invalid run_id format."}), 400

    run = _run_store.get(run_id)
    if run is None:
        return jsonify({"error": "Run not found."}), 404

    return jsonify({
        "run_id":   run_id,
        "status":   run.get("status",   "unknown"),
        "progress": run.get("progress", 0),
        "logs":     run.get("logs",     []),
    }), 200


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # SECURITY: Debug mode intentionally disabled outside dev.
    #           Set FLASK_ENV=development locally to enable debug.
    debug = os.getenv("FLASK_ENV", "production") == "development"
    app.run(host="0.0.0.0", port=5000, debug=debug)
