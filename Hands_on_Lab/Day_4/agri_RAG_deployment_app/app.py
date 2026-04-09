"""
AgriSage — RAG Backend
FastAPI · FAISS · sentence-transformers · OpenAI GPT
Endpoints: GET /health  POST /ingest  POST /ask  GET /weather
"""

import os, json, uuid, logging
from pathlib import Path
from typing   import List, Optional

import numpy  as np
import faiss
import httpx

from fastapi            import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses  import JSONResponse
from pydantic           import BaseModel

import pdfplumber
from sentence_transformers import SentenceTransformer
from openai import OpenAI

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("agrisage")

# ── Config ────────────────────────────────────────────────────────
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
CORS_ORIGINS     = os.getenv("CORS_ORIGINS", "*").split(",")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
CHUNK_SIZE       = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP    = int(os.getenv("CHUNK_OVERLAP", "150"))
TOP_K            = int(os.getenv("TOP_K", "5"))
INDEX_PATH       = Path(os.getenv("INDEX_PATH", "./faiss_index"))
GPT_MODEL        = os.getenv("GPT_MODEL", "gpt-4o-mini")

# ── FastAPI App ───────────────────────────────────────────────────
app = FastAPI(title="AgriSage RAG API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global State ──────────────────────────────────────────────────
embed_model:  Optional[SentenceTransformer] = None
faiss_index:  Optional[faiss.IndexFlatIP]   = None   # inner-product (cosine after norm)
chunk_store:  List[dict]                    = []      # [{id, text, source, page}]
openai_client: Optional[OpenAI]             = None

# ── Startup ───────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    global embed_model, faiss_index, chunk_store, openai_client

    log.info("Loading embedding model: %s", EMBED_MODEL_NAME)
    embed_model = SentenceTransformer(EMBED_MODEL_NAME)

    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        log.info("OpenAI client ready.")
    else:
        log.warning("OPENAI_API_KEY not set — /ask will return structured placeholder.")

    # Load persisted index if exists
    _load_index()
    log.info("AgriSage backend ready. Chunks in store: %d", len(chunk_store))

# ── Index Persistence ─────────────────────────────────────────────
def _save_index():
    INDEX_PATH.mkdir(parents=True, exist_ok=True)
    if faiss_index:
        faiss.write_index(faiss_index, str(INDEX_PATH / "index.faiss"))
    with open(INDEX_PATH / "chunks.json", "w") as f:
        json.dump(chunk_store, f, ensure_ascii=False)
    log.info("Index saved: %d chunks", len(chunk_store))

def _load_index():
    global faiss_index, chunk_store
    idx_file   = INDEX_PATH / "index.faiss"
    chunk_file = INDEX_PATH / "chunks.json"
    if idx_file.exists() and chunk_file.exists():
        faiss_index = faiss.read_index(str(idx_file))
        with open(chunk_file) as f:
            chunk_store = json.load(f)
        log.info("Loaded persisted index: %d chunks", len(chunk_store))

# ── Text Chunking ─────────────────────────────────────────────────
def _chunk_text(text: str, source: str, page: int) -> List[dict]:
    chunks = []
    start  = 0
    while start < len(text):
        end   = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()
        if len(chunk) > 80:          # skip tiny fragments
            chunks.append({
                "id":     str(uuid.uuid4())[:8],
                "text":   chunk,
                "source": source,
                "page":   page,
            })
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks

# ── Embedding Helpers ─────────────────────────────────────────────
def _embed(texts: List[str]) -> np.ndarray:
    vecs = embed_model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    # L2-normalise for cosine similarity via inner product
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-10
    return (vecs / norms).astype("float32")

# ── /health ───────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status":       "ok",
        "ingested_docs": len(set(c["source"] for c in chunk_store)),
        "total_chunks":  len(chunk_store),
        "model":         EMBED_MODEL_NAME,
        "llm_ready":     openai_client is not None,
    }

# ── /ingest ───────────────────────────────────────────────────────
@app.post("/ingest")
async def ingest(files: List[UploadFile] = File(...)):
    global faiss_index, chunk_store

    new_chunks: List[dict] = []

    for upload in files:
        if not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"{upload.filename} is not a PDF")

        raw = await upload.read()
        tmp = Path(f"/tmp/{uuid.uuid4().hex}.pdf")
        tmp.write_bytes(raw)

        try:
            with pdfplumber.open(str(tmp)) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    if text.strip():
                        new_chunks.extend(_chunk_text(text, upload.filename, page_num))
        finally:
            tmp.unlink(missing_ok=True)

    if not new_chunks:
        raise HTTPException(422, "No extractable text found in uploaded PDFs.")

    # Embed new chunks
    texts = [c["text"] for c in new_chunks]
    vecs  = _embed(texts)

    dim = vecs.shape[1]
    if faiss_index is None:
        faiss_index = faiss.IndexFlatIP(dim)

    faiss_index.add(vecs)
    chunk_store.extend(new_chunks)
    _save_index()

    return {
        "status": "ok",
        "files":  len(files),
        "chunks": len(new_chunks),
        "total":  len(chunk_store),
    }

# ── /ask Request Model ────────────────────────────────────────────
class AskRequest(BaseModel):
    location:      Optional[str] = ""
    crop:          str
    season:        Optional[str] = ""
    symptoms:      str
    soil_type:     Optional[str] = ""
    last_rainfall: Optional[str] = ""

# ── RAG Retrieval ─────────────────────────────────────────────────
def _retrieve(query: str, top_k: int = TOP_K):
    if faiss_index is None or faiss_index.ntotal == 0:
        return [], 0.0

    q_vec = _embed([query])
    scores, indices = faiss_index.search(q_vec, min(top_k, faiss_index.ntotal))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx >= 0 and idx < len(chunk_store):
            results.append({**chunk_store[idx], "score": float(score)})

    avg_score = float(np.mean([r["score"] for r in results])) if results else 0.0
    return results, avg_score

# ── /ask ──────────────────────────────────────────────────────────
@app.post("/ask")
async def ask(req: AskRequest):
    query = (
        f"Crop: {req.crop}. Location: {req.location}. Season: {req.season}. "
        f"Observed symptoms: {req.symptoms}. Soil type: {req.soil_type}. "
        f"Last rainfall/irrigation: {req.last_rainfall}."
    )

    retrieved, avg_score = _retrieve(query)
    low_confidence       = avg_score < 0.30 or len(retrieved) == 0

    # Build context block
    context_parts = []
    for i, chunk in enumerate(retrieved):
        context_parts.append(
            f"[Source {i+1}: {chunk['source']}, page {chunk['page']}, chunk {chunk['id']}]\n{chunk['text']}"
        )
    context_block = "\n\n---\n\n".join(context_parts) if context_parts else "No documents retrieved."

    citations = [
        {"source": c["source"], "chunk_id": c["id"], "snippet": c["text"][:120], "score": round(c["score"], 3)}
        for c in retrieved
    ]

    # ── Prompt ────────────────────────────────────────────────────
    system_prompt = """You are AgriSage, a knowledgeable agricultural advisor helping farmers with crop diseases, 
soil treatment, pest control, and seasonal planning. You answer in simple, actionable language.

RULES:
- Provide a structured JSON response only (no markdown fences).
- Use the retrieved context as your primary source. If context is insufficient, use general best practices but flag low confidence.
- Never invent specific chemical dosages — say "consult local label/regulations".
- Always include a disclaimer about consulting local agricultural officers.
- Respond ONLY with valid JSON matching the schema below.

JSON SCHEMA:
{
  "summary": "1-2 sentence overview of the situation",
  "likely_causes": ["cause 1", "cause 2"],
  "action_plan": ["Step 1: ...", "Step 2: ...", "Step 3: ..."],
  "preventive_measures": ["measure 1", "measure 2"],
  "monitor_next_7_days": ["watch for ...", "check ..."],
  "low_confidence": false
}"""

    user_prompt = f"""Farmer's context:
Location: {req.location or 'Not specified'}
Crop: {req.crop}
Season stage: {req.season or 'Not specified'}
Observed symptoms: {req.symptoms}
Soil type: {req.soil_type or 'Not specified'}
Last rainfall/irrigation: {req.last_rainfall or 'Not specified'}

RETRIEVED KNOWLEDGE BASE CONTEXT:
{context_block}

Confidence score: {avg_score:.2f} (below 0.30 = low confidence)

Provide your structured agricultural advice as JSON."""

    # ── Generate ──────────────────────────────────────────────────
    if openai_client:
        try:
            completion = openai_client.chat.completions.create(
                model=GPT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content
            answer = json.loads(raw)
        except Exception as e:
            log.error("OpenAI error: %s", e)
            answer = _fallback_answer(req, low_confidence)
    else:
        answer = _fallback_answer(req, low_confidence)

    answer["citations"]      = citations
    answer["low_confidence"] = low_confidence
    answer["retrieval_score"]= round(avg_score, 3)
    return JSONResponse(content=answer)

# ── Fallback (no OpenAI key) ──────────────────────────────────────
def _fallback_answer(req: AskRequest, low_confidence: bool) -> dict:
    return {
        "summary":          f"You reported symptoms on your {req.crop} crop ({req.season} stage). "
                            f"Without OpenAI configured, detailed AI analysis is unavailable, but general guidance follows.",
        "likely_causes":    ["Fungal disease", "Nutritional deficiency", "Pest infestation", "Environmental stress"],
        "action_plan":      [
            "Step 1: Isolate affected plants to prevent spread.",
            "Step 2: Remove and destroy visibly infected/infested plant material.",
            "Step 3: Identify the pathogen or pest precisely (collect samples if possible).",
            "Step 4: Apply appropriate treatment per local product label.",
            "Step 5: Improve field drainage and air circulation.",
        ],
        "preventive_measures": [
            "Use certified disease-free seeds.",
            "Rotate crops each season to break pest/disease cycles.",
            "Maintain proper plant spacing for airflow.",
            "Monitor weather and irrigate at optimal times.",
        ],
        "monitor_next_7_days": [
            "Check for spread of symptoms to new leaves or plants.",
            "Monitor for secondary pest activity.",
            "Record daily temperature and humidity if possible.",
            "Re-assess after any rainfall event.",
        ],
        "low_confidence": low_confidence,
    }

# ── /weather ─────────────────────────────────────────────────────
@app.get("/weather")
async def weather(location: str, key: str):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={key}&units=metric"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url)
        d = r.json()
        if r.status_code != 200:
            raise HTTPException(400, d.get("message", "Weather API error"))
        return {
            "temp":        d["main"]["temp"],
            "humidity":    d["main"]["humidity"],
            "description": d["weather"][0]["description"].title(),
            "wind_kph":    round(d["wind"]["speed"] * 3.6, 1),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Weather fetch failed: {e}")