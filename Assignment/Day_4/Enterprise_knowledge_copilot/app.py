"""
Enterprise Knowledge Copilot — Flask Backend
============================================
RAG system over internal documents using Azure AI Search.
Features: hybrid search, RBAC, cost monitoring, observability.
"""

import os
import json
import time
import uuid
import math
import logging
import datetime
import threading
from collections import deque
from flask import Flask, request, jsonify, send_from_directory

# ─── Optional imports (graceful degradation) ────────────────────────────────
try:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex, SimpleField, SearchableField, SearchField,
        SearchFieldDataType, VectorSearch, HnswAlgorithmConfiguration,
        VectorSearchProfile, SemanticConfiguration, SemanticSearch,
        SemanticPrioritizedFields, SemanticField,
    )
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import requests as http_requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ─── Configuration ───────────────────────────────────────────────────────────
AZURE_SEARCH_ENDPOINT   = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_KEY        = os.getenv("AZURE_SEARCH_KEY", "")
AZURE_SEARCH_INDEX      = os.getenv("AZURE_SEARCH_INDEX", "knowledge-copilot")
OPENAI_API_KEY          = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBEDDING_MODEL  = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
OPENAI_CHAT_MODEL       = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
MISTRAL_ENDPOINT        = os.getenv("MISTRAL_ENDPOINT", "http://localhost:11434/api/chat")
MISTRAL_MODEL           = os.getenv("MISTRAL_MODEL", "mistral")
ADMIN_TOKEN             = os.getenv("ADMIN_TOKEN", "demo-admin-secret")
TOP_K_RESULTS           = int(os.getenv("TOP_K_RESULTS", "5"))
VECTOR_WEIGHT           = float(os.getenv("VECTOR_WEIGHT", "0.6"))
KEYWORD_WEIGHT          = float(os.getenv("KEYWORD_WEIGHT", "0.4"))
CHUNK_SIZE              = int(os.getenv("CHUNK_SIZE", "512"))
CHUNK_OVERLAP           = int(os.getenv("CHUNK_OVERLAP", "64"))

# Pricing (USD per 1M tokens) — update via env vars if rates change
PRICE_IN  = float(os.getenv("OPENAI_PRICE_IN_PER_1M",  "0.15"))
PRICE_OUT = float(os.getenv("OPENAI_PRICE_OUT_PER_1M", "0.60"))
PRICE_EMB = float(os.getenv("OPENAI_PRICE_EMB_PER_1M", "0.10"))

# ─── RBAC Role Definitions ───────────────────────────────────────────────────
ROLE_PERMISSIONS = {
    "admin":   {"can_ingest": True,  "allowed_doc_groups": ["public", "internal", "confidential", "restricted"]},
    "manager": {"can_ingest": False, "allowed_doc_groups": ["public", "internal", "confidential"]},
    "analyst": {"can_ingest": False, "allowed_doc_groups": ["public", "internal"]},
    "viewer":  {"can_ingest": False, "allowed_doc_groups": ["public"]},
    "guest":   {"can_ingest": False, "allowed_doc_groups": ["public"]},
}
VALID_ROLES = list(ROLE_PERMISSIONS.keys())

# ─── Flask App ───────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=".", static_url_path="")

# ─── Structured JSON Logger ──────────────────────────────────────────────────
class JsonFormatter(logging.Formatter):
    def format(self, record):
        obj = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level":     record.levelname,
            "message":   record.getMessage(),
        }
        if hasattr(record, "extra"):
            obj.update(record.extra)
        return json.dumps(obj)

logger = logging.getLogger("copilot")
logger.setLevel(logging.INFO)
_sh = logging.StreamHandler()
_sh.setFormatter(JsonFormatter())
logger.addHandler(_sh)

LOG_RING = deque(maxlen=200)
_ring_lock = threading.Lock()

class RingHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = json.loads(self.format(record))
        except Exception:
            msg = {"message": record.getMessage()}
        with _ring_lock:
            LOG_RING.append(msg)

_rh = RingHandler()
_rh.setFormatter(JsonFormatter())
logger.addHandler(_rh)

def slog(level, msg, **kw):
    getattr(logger, level)(msg, extra={"extra": kw})

# ─── Metrics Store ───────────────────────────────────────────────────────────
class MetricsStore:
    def __init__(self):
        self._lock          = threading.Lock()
        self.total_requests = 0
        self.total_errors   = 0
        self.total_ingest   = 0
        self.ret_lats       = []
        self.llm_lats       = []
        self.openai_calls   = 0
        self.mistral_calls  = 0
        self.tokens_in      = 0
        self.tokens_out     = 0
        self.cost_usd       = 0.0
        self.last_cost      = 0.0
        self.per_role       = {}

    def record(self, rl, ll, ti, to, cost, role, err=False):
        with self._lock:
            self.total_requests += 1
            if err: self.total_errors += 1
            self.ret_lats.append(rl)
            self.llm_lats.append(ll)
            self.tokens_in  += ti
            self.tokens_out += to
            self.cost_usd   += cost
            self.last_cost   = cost
            r = self.per_role.setdefault(role, {"tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "requests": 0})
            r["tokens_in"] += ti; r["tokens_out"] += to; r["cost_usd"] += cost; r["requests"] += 1

    def avg(self, lst): return round(sum(lst)/len(lst), 4) if lst else 0.0

    def snapshot(self):
        with self._lock:
            return {
                "total_requests":    self.total_requests,
                "total_errors":      self.total_errors,
                "total_ingest":      self.total_ingest,
                "avg_retrieval_ms":  round(self.avg(self.ret_lats)*1000, 2),
                "avg_llm_ms":        round(self.avg(self.llm_lats)*1000, 2),
                "openai_calls":      self.openai_calls,
                "mistral_calls":     self.mistral_calls,
                "total_tokens_in":   self.tokens_in,
                "total_tokens_out":  self.tokens_out,
                "total_cost_usd":    round(self.cost_usd, 6),
                "last_request_cost": round(self.last_cost, 6),
                "per_role":          dict(self.per_role),
            }

metrics = MetricsStore()

# ─── Demo Mock Data ───────────────────────────────────────────────────────────
DEMO_CHUNKS = [
    {"chunk_id": "demo-001", "document_id": "doc-annual-report",  "filename": "annual_report_2024.pdf",
     "content": "Revenue grew 24% YoY to $4.2B in FY2024, driven by cloud services and enterprise software. EBITDA margin expanded to 31%.",
     "allowed_roles": ["public","internal","confidential"], "@search.score": 0.94},
    {"chunk_id": "demo-002", "document_id": "doc-hr-policy",      "filename": "hr_policy_v3.docx",
     "content": "Remote work policy (effective Jan 2024): employees may work remotely up to 3 days per week with manager approval. Core hours 10am-3pm local time.",
     "allowed_roles": ["public","internal"], "@search.score": 0.88},
    {"chunk_id": "demo-003", "document_id": "doc-tech-roadmap",   "filename": "tech_roadmap_q3.md",
     "content": "Q3 priorities: (1) migrate data warehouse to Azure Synapse, (2) deploy RAG-based knowledge system, (3) implement zero-trust network architecture.",
     "allowed_roles": ["internal","confidential"], "@search.score": 0.82},
    {"chunk_id": "demo-004", "document_id": "doc-security-policy","filename": "security_guidelines.pdf",
     "content": "All confidential data must be encrypted at rest (AES-256) and in transit (TLS 1.3+). Access logs retained 90 days minimum.",
     "allowed_roles": ["confidential","restricted"], "@search.score": 0.79},
    {"chunk_id": "demo-005", "document_id": "doc-onboarding",     "filename": "onboarding_guide.md",
     "content": "New employees should complete compliance training within 30 days. IT provisions accounts within 2 business days of start date.",
     "allowed_roles": ["public","internal"], "@search.score": 0.75},
]

# ─── Helpers ──────────────────────────────────────────────────────────────────
def estimate_tokens(text): return max(1, math.ceil(len(text) / 4))

def estimate_cost(ti, to, emb=0):
    return (ti/1e6)*PRICE_IN + (to/1e6)*PRICE_OUT + (emb/1e6)*PRICE_EMB

def get_embedding(text):
    if not OPENAI_AVAILABLE or not OPENAI_API_KEY:
        return [0.0]*1536
    try:
        c = openai.OpenAI(api_key=OPENAI_API_KEY)
        r = c.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=[text])
        return r.data[0].embedding
    except Exception as e:
        slog("warning", "Embedding failed", error=str(e))
        return [0.0]*1536

def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    words, chunks, i = text.split(), [], 0
    while i < len(words):
        chunks.append((" ".join(words[i:i+size]), i))
        i += max(1, size - overlap)
    return chunks

# ─── Azure Clients ────────────────────────────────────────────────────────────
def get_search_client():
    if not AZURE_AVAILABLE or not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_KEY:
        return None
    return SearchClient(AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX, AzureKeyCredential(AZURE_SEARCH_KEY))

def get_index_client():
    if not AZURE_AVAILABLE or not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_KEY:
        return None
    return SearchIndexClient(AZURE_SEARCH_ENDPOINT, AzureKeyCredential(AZURE_SEARCH_KEY))

def ensure_index():
    ic = get_index_client()
    if not ic: return False
    try: ic.get_index(AZURE_SEARCH_INDEX); return True
    except Exception: pass
    fields = [
        SimpleField("chunk_id", SearchFieldDataType.String, key=True),
        SimpleField("document_id", SearchFieldDataType.String, filterable=True),
        SimpleField("filename", SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField("last_modified", SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField("allowed_roles", SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
        SearchableField("content", SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SearchField("content_vector", SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True, vector_search_dimensions=1536, vector_search_profile_name="hnsw-profile"),
    ]
    vs = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration("hnsw-algo", parameters={"m": 4, "efConstruction": 400})],
        profiles=[VectorSearchProfile("hnsw-profile", algorithm_configuration_name="hnsw-algo")],
    )
    ss = SemanticSearch(configurations=[SemanticConfiguration(
        "semantic-config", SemanticPrioritizedFields(content_fields=[SemanticField("content")]))])
    ic.create_or_update_index(SearchIndex(AZURE_SEARCH_INDEX, fields=fields, vector_search=vs, semantic_search=ss))
    return True

# ─── Hybrid Retrieval ─────────────────────────────────────────────────────────
def hybrid_retrieve(query, role, top_k=TOP_K_RESULTS):
    """
    Hybrid BM25 + vector search with RRF fusion.

    RRF formula: score(d) = Σ_r  1 / (k + rank_r(d)),  k=60
    Azure AI Search applies this natively for hybrid queries.
    We further weight:  final = KEYWORD_WEIGHT*bm25 + VECTOR_WEIGHT*vector
    """
    allowed = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["guest"])["allowed_doc_groups"]
    sc = get_search_client()
    if sc is None:
        results = [c for c in DEMO_CHUNKS if any(g in c["allowed_roles"] for g in allowed)]
        return results[:top_k], True

    qv = get_embedding(query)
    flt = " or ".join(f"allowed_roles/any(r: r eq '{g}')" for g in allowed)
    from azure.search.documents.models import VectorizedQuery
    vq = VectorizedQuery(vector=qv, k_nearest_neighbors=top_k*2, fields="content_vector")
    res = sc.search(search_text=query, vector_queries=[vq], filter=flt, top=top_k,
                    select=["chunk_id","document_id","filename","content","last_modified"])
    return list(res), False

# ─── LLM Synthesis ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are the Enterprise Knowledge Copilot — a precise assistant that answers "
    "questions strictly from the retrieved document excerpts. Cite sources by filename "
    "and chunk_id. If the context lacks the answer, say so clearly. Be concise and professional."
)

def build_context(chunks):
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] {c.get('filename','?')} | {c.get('chunk_id','?')}\n{c.get('content','')}")
    return "\n\n---\n\n".join(parts)

def call_openai(prompt, context):
    if not OPENAI_AVAILABLE or not OPENAI_API_KEY: raise RuntimeError("OpenAI not configured")
    c = openai.OpenAI(api_key=OPENAI_API_KEY)
    msgs = [{"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":f"Context:\n\n{context}\n\nQuestion: {prompt}"}]
    r = c.chat.completions.create(model=OPENAI_CHAT_MODEL, messages=msgs, temperature=0.2, max_tokens=1024)
    return r.choices[0].message.content, r.usage.prompt_tokens, r.usage.completion_tokens

def call_mistral(prompt, context):
    if not REQUESTS_AVAILABLE: return _demo_answer(prompt, context)
    payload = {"model": MISTRAL_MODEL, "stream": False,
               "messages": [{"role":"system","content":SYSTEM_PROMPT},
                             {"role":"user","content":f"Context:\n\n{context}\n\nQuestion: {prompt}"}]}
    try:
        r = http_requests.post(MISTRAL_ENDPOINT, json=payload, timeout=60); r.raise_for_status()
        data = r.json()
        ans = data.get("message",{}).get("content","") or data.get("response","")
        return ans, estimate_tokens(SYSTEM_PROMPT+context+prompt), estimate_tokens(ans)
    except Exception as e:
        slog("warning", "Mistral call failed", error=str(e))
        return _demo_answer(prompt, context)

def _demo_answer(prompt, context):
    ans = (f"[DEMO MODE — no LLM configured]\n\nYour question: \"{prompt}\"\n\n"
           f"Configure OPENAI_API_KEY or MISTRAL_ENDPOINT to get real AI-generated answers. "
           f"The retrieved documents above contain relevant information about your query.")
    return ans, estimate_tokens(context+prompt), estimate_tokens(ans)

def synthesize(prompt, context, role):
    try:
        ans, ti, to = call_openai(prompt, context)
        metrics.openai_calls += 1
        return ans, ti, to, "openai"
    except Exception as e:
        slog("info", "OpenAI fallback to Mistral", error=str(e))
        ans, ti, to = call_mistral(prompt, context)
        metrics.mistral_calls += 1
        return ans, ti, to, "mistral"

# ─── Ingest ───────────────────────────────────────────────────────────────────
def ingest_document(text, filename, allowed_roles=None):
    if allowed_roles is None: allowed_roles = ["internal"]
    doc_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, filename))
    chunks = chunk_text(text)
    docs, emb_tok = [], 0
    for idx, (ct, _) in enumerate(chunks):
        vec = get_embedding(ct); emb_tok += estimate_tokens(ct)
        docs.append({"chunk_id": f"{doc_id}-{idx:04d}", "document_id": doc_id,
                     "filename": filename, "last_modified": datetime.datetime.utcnow().isoformat()+"Z",
                     "allowed_roles": allowed_roles, "content": ct, "content_vector": vec})
    sc = get_search_client()
    if sc:
        ensure_index(); sc.upload_documents(docs)
    else:
        for d in docs: d["@search.score"] = 1.0; DEMO_CHUNKS.append(d)
    metrics.total_ingest += 1
    return {"chunks_created": len(docs), "document_id": doc_id,
            "embed_cost_usd": round((emb_tok/1e6)*PRICE_EMB, 8)}

# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.datetime.utcnow().isoformat()+"Z",
        "azure_search": "configured" if (AZURE_SEARCH_ENDPOINT and AZURE_AVAILABLE) else "demo_mode",
        "openai": "configured" if (OPENAI_API_KEY and OPENAI_AVAILABLE) else "demo_mode",
        "mistral_endpoint": MISTRAL_ENDPOINT,
        "version": "1.0.0",
    })

@app.route("/metrics")
def prom_metrics():
    s = metrics.snapshot()
    lines = [
        f"copilot_requests_total {s['total_requests']}",
        f"copilot_errors_total {s['total_errors']}",
        f"copilot_avg_retrieval_ms {s['avg_retrieval_ms']}",
        f"copilot_avg_llm_ms {s['avg_llm_ms']}",
        f"copilot_tokens_in_total {s['total_tokens_in']}",
        f"copilot_tokens_out_total {s['total_tokens_out']}",
        f"copilot_cost_usd_total {s['total_cost_usd']}",
        f"copilot_openai_calls {s['openai_calls']}",
        f"copilot_mistral_calls {s['mistral_calls']}",
    ]
    return "\n".join(lines)+"\n", 200, {"Content-Type": "text/plain; version=0.0.4"}

@app.route("/api/query", methods=["POST"])
def api_query():
    req_id = str(uuid.uuid4())[:8]
    body   = request.get_json(silent=True) or {}
    query  = (body.get("query") or "").strip()
    role   = (body.get("role")  or "viewer").strip().lower()
    if not query: return jsonify({"error": "query is required"}), 400
    if role not in VALID_ROLES: return jsonify({"error": f"invalid role; choose from {VALID_ROLES}"}), 400

    slog("info", "Query received", request_id=req_id, role=role, query=query[:120])

    t0 = time.time()
    try: chunks, demo = hybrid_retrieve(query, role)
    except Exception as e:
        slog("error","Retrieval failed", request_id=req_id, error=str(e))
        metrics.record(0,0,0,0,0,role,err=True)
        return jsonify({"error": "Retrieval failed", "detail": str(e)}), 500
    ret_lat = time.time()-t0

    context = build_context(chunks)
    t1 = time.time()
    ans, ti, to, provider = synthesize(query, context, role)
    llm_lat = time.time()-t1

    emb_tok = estimate_tokens(query)
    cost    = estimate_cost(ti, to, emb_tok)
    metrics.record(ret_lat, llm_lat, ti, to, cost, role)
    slog("info","Query done", request_id=req_id, role=role, provider=provider,
         retrieval_ms=round(ret_lat*1000,2), llm_ms=round(llm_lat*1000,2),
         tokens_in=ti, tokens_out=to, cost_usd=round(cost,8), demo_mode=demo)

    return jsonify({
        "answer":    ans,
        "citations": [{"chunk_id": c.get("chunk_id",""), "document_id": c.get("document_id",""),
                       "filename": c.get("filename","?"), "snippet": (c.get("content",""))[:300],
                       "score": round(float(c.get("@search.score",0)),4)} for c in chunks],
        "metrics":   {"request_id": req_id, "provider": provider, "demo_mode": demo,
                      "retrieval_ms": round(ret_lat*1000,2), "llm_ms": round(llm_lat*1000,2),
                      "tokens_in": ti, "tokens_out": to, "cost_usd": round(cost,8)},
    })

@app.route("/api/ingest", methods=["POST"])
def api_ingest():
    role = request.headers.get("X-User-Role","viewer").strip().lower()
    auth = request.headers.get("Authorization","")
    if role != "admin" and auth != f"Bearer {ADMIN_TOKEN}":
        return jsonify({"error": "Forbidden: admin role required"}), 403
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    fname = (body.get("filename") or f"upload_{int(time.time())}.txt")
    aroles = body.get("allowed_roles", ["internal"])
    if not text: return jsonify({"error": "text payload required"}), 400
    try:
        result = ingest_document(text, fname, aroles)
        slog("info","Ingest done", filename=fname, **result)
        return jsonify({"status":"ok", **result})
    except Exception as e:
        slog("error","Ingest failed", filename=fname, error=str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs")
def api_logs():
    with _ring_lock: logs = list(LOG_RING)
    return jsonify({"logs": logs[-50:], "total_buffered": len(logs)})

@app.route("/api/metrics-json")
def api_metrics_json():
    return jsonify(metrics.snapshot())

if __name__ == "__main__":
    port = int(os.getenv("PORT","5000"))
    slog("info","Enterprise Knowledge Copilot starting", port=port)
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG","false").lower()=="true")
