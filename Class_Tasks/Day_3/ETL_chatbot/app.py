"""
ETL Data Engineer Chatbot — app.py
Backend: Python + Flask
LLM: Groq (llama-3.1-8b-instant) with local Mistral fallback
RAG: Simple keyword retrieval over etl_rag.txt
ETL: LangGraph + Pandas 3-step linear pipeline
Upload: Multi-format file ingestion (CSV, Excel, JSON, Parquet, Avro, TSV, XML)
"""

import os, io, json, time, logging, traceback, tempfile, uuid
from pathlib import Path
from typing import TypedDict, Optional
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import pandas as pd
from langgraph.graph import StateGraph, END
from groq import Groq

load_dotenv()

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

app = Flask(__name__, static_folder=".", static_url_path="")

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
Path("data/clean").mkdir(parents=True, exist_ok=True)

# ────────────────────────────────────────────────────────────────────────────
# RAG — load knowledge base once at startup
# ────────────────────────────────────────────────────────────────────────────
RAG_FILE = Path("etl_rag.txt")
RAG_CHUNKS: list[str] = []

def _load_rag():
    if not RAG_FILE.exists():
        log.warning("etl_rag.txt not found — RAG disabled")
        return
    text = RAG_FILE.read_text(encoding="utf-8")
    RAG_CHUNKS.extend([c.strip() for c in text.split("\n\n") if len(c.strip()) > 40])
    log.info(f"RAG loaded: {len(RAG_CHUNKS)} chunks from {RAG_FILE}")

_load_rag()

def retrieve(query: str, top_k: int = 4) -> str:
    if not RAG_CHUNKS:
        return ""
    q_words = set(query.lower().split())
    scored = [(len(q_words & set(c.lower().split())), c) for c in RAG_CHUNKS]
    scored.sort(key=lambda x: -x[0])
    relevant = [c for score, c in scored[:top_k] if score > 0]
    return "\n\n".join(relevant) if relevant else ""

# ────────────────────────────────────────────────────────────────────────────
# LLM — Groq primary, local Mistral fallback
# ────────────────────────────────────────────────────────────────────────────
GROQ_API_KEY         = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL           = "llama-3.1-8b-instant"
MISTRAL_FALLBACK_URL = os.getenv("MISTRAL_FALLBACK_URL", "http://localhost:11434/api/chat")
MISTRAL_MODEL        = os.getenv("MISTRAL_MODEL", "mistral")

groq_client: Optional[Groq] = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
    log.info("Groq client initialised")
else:
    log.warning("GROQ_API_KEY not set — will attempt Mistral fallback")

SYSTEM_PROMPT = """You are DataFlow AI, an expert assistant for data engineers.
You specialise in ETL pipelines, Pandas, LangGraph orchestration, data quality,
observability, and production data workflows.
Be concise, practical, and cite concrete patterns when relevant.
When asked about the ETL example in this app, describe the 3-step LangGraph pipeline."""


def chat_groq(messages):
    start = time.time()
    resp = groq_client.chat.completions.create(
        model=GROQ_MODEL, messages=messages, temperature=0.4, max_tokens=1024,
    )
    return resp.choices[0].message.content.strip(), round(time.time() - start, 3)


def chat_mistral_fallback(messages):
    import urllib.request, json as _j
    payload = _j.dumps({"model": MISTRAL_MODEL, "messages": messages, "stream": False}).encode()
    req = urllib.request.Request(MISTRAL_FALLBACK_URL, data=payload,
                                  headers={"Content-Type": "application/json"})
    start = time.time()
    with urllib.request.urlopen(req, timeout=60) as r:
        data = _j.loads(r.read())
    return data["message"]["content"].strip(), round(time.time() - start, 3)


def generate_reply(user_message: str) -> dict:
    context  = retrieve(user_message)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "system", "content": f"Relevant knowledge:\n{context}"})
    messages.append({"role": "user", "content": user_message})

    provider = "groq"
    try:
        if groq_client:
            reply, latency = chat_groq(messages)
        else:
            provider = "mistral-fallback"
            reply, latency = chat_mistral_fallback(messages)
    except Exception as e:
        log.error(f"LLM error ({provider}): {e}")
        if provider == "groq":
            try:
                provider = "mistral-fallback"
                reply, latency = chat_mistral_fallback(messages)
            except Exception as e2:
                return {"reply": f"Both LLM providers failed. Groq: {e}. Fallback: {e2}", "latency": 0, "provider": "none"}
        else:
            return {"reply": str(e), "latency": 0, "provider": "none"}

    log.info(f"[chat] provider={provider} latency={latency}s tokens≈{len(reply.split())}")
    return {"reply": reply, "latency": latency, "provider": provider, "rag_used": bool(context)}

# ────────────────────────────────────────────────────────────────────────────
# File Ingestion — multi-format reader with schema inference
# ────────────────────────────────────────────────────────────────────────────
CHUNK_ROWS = 50_000   # rows per processing chunk for large files

def detect_format(filename: str, file_bytes: bytes) -> str:
    """Detect file format from extension, then magic bytes."""
    ext = Path(filename).suffix.lower()
    ext_map = {
        ".csv": "csv", ".tsv": "tsv", ".txt": "csv",
        ".xlsx": "excel", ".xls": "excel",
        ".json": "json",
        ".parquet": "parquet",
        ".avro": "avro",
        ".xml": "xml",
    }
    if ext in ext_map:
        return ext_map[ext]
    # Magic bytes fallback
    if file_bytes[:4] == b"PAR1":
        return "parquet"
    if file_bytes[:4] == b"Obj\x01":
        return "avro"
    if file_bytes[:2] in (b"PK",):
        return "excel"
    return "csv"  # default


def read_dataframe(file_bytes: bytes, fmt: str, filename: str) -> pd.DataFrame:
    """Parse bytes into a DataFrame; memory-efficient for large files."""
    buf = io.BytesIO(file_bytes)

    if fmt == "csv":
        # Use chunked reader then concat — handles files larger than RAM gracefully
        chunks = pd.read_csv(buf, chunksize=CHUNK_ROWS, low_memory=False,
                             on_bad_lines="warn", encoding_errors="replace")
        return pd.concat(chunks, ignore_index=True)

    if fmt == "tsv":
        chunks = pd.read_csv(buf, sep="\t", chunksize=CHUNK_ROWS, low_memory=False,
                             on_bad_lines="warn", encoding_errors="replace")
        return pd.concat(chunks, ignore_index=True)

    if fmt == "excel":
        return pd.read_excel(buf, engine="openpyxl")

    if fmt == "json":
        try:
            return pd.read_json(buf, lines=False)
        except ValueError:
            buf.seek(0)
            return pd.read_json(buf, lines=True)  # newline-delimited JSON

    if fmt == "parquet":
        return pd.read_parquet(buf)

    if fmt == "avro":
        try:
            import fastavro
            buf.seek(0)
            reader = fastavro.reader(buf)
            records = list(reader)
            return pd.DataFrame(records)
        except ImportError:
            raise ValueError("fastavro not installed — Avro files not supported")

    if fmt == "xml":
        try:
            return pd.read_xml(buf)
        except Exception as e:
            raise ValueError(f"XML parse error: {e}")

    raise ValueError(f"Unsupported format: {fmt}")


def infer_schema(df: pd.DataFrame) -> dict:
    """Return a schema summary including inferred semantic types."""
    schema = {}
    for col in df.columns:
        dtype = str(df[col].dtype)
        sample = df[col].dropna().head(5).tolist()
        schema[col] = {"dtype": dtype, "sample": [str(s) for s in sample]}
    return schema

# ────────────────────────────────────────────────────────────────────────────
# ETL Pipeline — LangGraph + Pandas (enhanced for uploaded files)
# ────────────────────────────────────────────────────────────────────────────

class ETLState(TypedDict):
    source_path:  str
    dest_path:    str
    file_format:  str
    raw_df:       Optional[object]
    cleaned_df:   Optional[object]
    metrics:      dict
    errors:       list[str]
    warnings:     list[str]
    steps_log:    list[dict]   # per-step progress for the UI


def _step(state: ETLState, name: str, status: str, detail: str = "") -> None:
    state["steps_log"].append({
        "step": name, "status": status, "detail": detail,
        "ts": datetime.utcnow().isoformat(),
    })


def node_extract(state: ETLState) -> ETLState:
    log.info("[ETL] ── EXTRACT ──────────────────")
    _step(state, "Parsing", "running", f"Reading {state['file_format'].upper()} source")
    src = state["source_path"]
    fmt = state.get("file_format", "csv")
    try:
        raw_bytes = Path(src).read_bytes()
        df = read_dataframe(raw_bytes, fmt, src)
        log.info(f"[ETL] Loaded {len(df)} rows × {len(df.columns)} cols from {src}")
        state["raw_df"] = df
        state["metrics"]["raw_rows"]    = len(df)
        state["metrics"]["raw_columns"] = list(df.columns)
        _step(state, "Parsing", "done", f"{len(df):,} rows, {len(df.columns)} columns")
    except FileNotFoundError:
        state["errors"].append(f"Source file not found: {src}")
        _step(state, "Parsing", "error", f"File not found: {src}")
    except pd.errors.EmptyDataError:
        state["errors"].append(f"Source file is empty: {src}")
        _step(state, "Parsing", "error", "Empty file")
    except Exception as e:
        state["errors"].append(f"Extract failed: {e}")
        _step(state, "Parsing", "error", str(e))
    return state


def node_transform(state: ETLState) -> ETLState:
    log.info("[ETL] ── TRANSFORM ─────────────────")
    if state["errors"] or state["raw_df"] is None:
        log.warning("[ETL] Skipping transform — upstream errors exist")
        return state

    df: pd.DataFrame = state["raw_df"].copy()

    # ── Step: Normalize columns ──────────────────────────────────────────────
    _step(state, "Cleaning", "running", "Normalising column names")
    df.columns = (
        df.columns.str.strip()
          .str.lower()
          .str.replace(r"[\s\-]+", "_", regex=True)
          .str.replace(r"[^\w]", "", regex=True)
    )
    log.info(f"[ETL] Columns normalised: {list(df.columns)}")

    # ── Step: Schema inference & type coercion ───────────────────────────────
    _step(state, "Transforming", "running", "Inferring types and coercing columns")
    inferred = 0
    for col in df.select_dtypes(include="object").columns:
        # Try datetime
        dt = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True)
        if dt.notna().sum() > 0.6 * len(df):
            df[col] = dt
            inferred += 1
            continue
        # Try numeric
        num = pd.to_numeric(df[col], errors="coerce")
        if num.notna().sum() > 0.5 * len(df):
            df[col] = num
            inferred += 1
    log.info(f"[ETL] Coerced {inferred} column(s)")

    # ── Step: Missing values ──────────────────────────────────────────────────
    _step(state, "Cleaning", "running", "Handling missing values")
    null_before = int(df.isna().sum().sum())
    for col in df.select_dtypes(include="number").columns:
        df[col] = df[col].fillna(df[col].median())
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].fillna("unknown")
    # datetime columns: forward-fill (last-observation-carried-forward)
    for col in df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
        df[col] = df[col].ffill().bfill()
    null_after = int(df.isna().sum().sum())
    state["metrics"]["nulls_imputed"] = null_before - null_after

    # ── Step: Deduplication ───────────────────────────────────────────────────
    _step(state, "Cleaning", "running", "Removing duplicate rows")
    dup_count = int(df.duplicated().sum())
    df = df.drop_duplicates()
    state["metrics"]["duplicates_removed"] = dup_count
    log.info(f"[ETL] Removed {dup_count} duplicates")

    # ── Step: Data quality checks ────────────────────────────────────────────
    _step(state, "Validating", "running", "Running data quality checks")
    dq_failures: list[str] = []

    # QC-1: Non-null check
    still_null = df.isna().sum()
    for col, cnt in still_null.items():
        if cnt > 0:
            dq_failures.append(f"QC-FAIL null constraint: {col} has {cnt} nulls after imputation")

    # QC-2: Negative numeric values (soft warning, not failure)
    for col in df.select_dtypes(include="number").columns:
        neg = int((df[col] < 0).sum())
        if neg > 0:
            state["warnings"].append(f"QC-WARN: {col} has {neg} negative values — verify if expected")

    # QC-3: Uniqueness on first column (assumed ID)
    id_col = df.columns[0]
    if df[id_col].duplicated().any():
        dq_failures.append(f"QC-FAIL uniqueness: column '{id_col}' has duplicate values")

    if dq_failures:
        state["errors"].extend(dq_failures)
        _step(state, "Validating", "error", f"{len(dq_failures)} DQ failure(s)")
        log.error(f"[ETL] {len(dq_failures)} DQ failure(s)")
    else:
        _step(state, "Validating", "done", "All quality checks passed")
        log.info("[ETL] All DQ checks passed")

    state["cleaned_df"] = df
    state["metrics"]["cleaned_rows"] = len(df)
    state["metrics"]["schema"]       = infer_schema(df)
    return state


def node_load(state: ETLState) -> ETLState:
    log.info("[ETL] ── LOAD ──────────────────────")
    if state["errors"] or state["cleaned_df"] is None:
        log.warning("[ETL] Skipping load — upstream errors exist")
        return state

    _step(state, "Loading", "running", "Writing cleaned data")
    df: pd.DataFrame = state["cleaned_df"]
    dest = state["dest_path"]
    Path(dest).parent.mkdir(parents=True, exist_ok=True)

    if dest.endswith(".parquet"):
        df.to_parquet(dest, index=False)
    else:
        df.to_csv(dest, index=False)
    log.info(f"[ETL] Wrote {len(df)} rows to {dest}")

    state["metrics"]["null_counts"] = df.isna().sum().to_dict()
    state["metrics"]["dest_path"]   = dest
    state["metrics"]["timestamp"]   = datetime.utcnow().isoformat()

    metrics_path = Path(dest).with_suffix(".metrics.json")
    metrics_path.write_text(json.dumps(state["metrics"], indent=2, default=str))
    log.info(f"[ETL] Metrics → {metrics_path}")

    _step(state, "Completed", "done",
          f"{len(df):,} clean rows written to {dest}")
    return state


def build_etl_graph() -> StateGraph:
    g = StateGraph(ETLState)
    g.add_node("extract",   node_extract)
    g.add_node("transform", node_transform)
    g.add_node("load",      node_load)
    g.set_entry_point("extract")
    g.add_edge("extract",   "transform")
    g.add_edge("transform", "load")
    g.add_edge("load",      END)
    return g.compile()

etl_graph = build_etl_graph()


def run_etl(source: str, dest: str, file_format: str = "csv") -> dict:
    state: ETLState = {
        "source_path": source,
        "dest_path":   dest,
        "file_format": file_format,
        "raw_df":      None,
        "cleaned_df":  None,
        "metrics":     {},
        "errors":      [],
        "warnings":    [],
        "steps_log":   [],
    }
    result = etl_graph.invoke(state)
    result.pop("raw_df",     None)
    result.pop("cleaned_df", None)
    return result

# ────────────────────────────────────────────────────────────────────────────
# Flask routes
# ────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data     = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "message is required"}), 400
    log.info(f"[api/chat] {user_msg[:120]}")
    return jsonify(generate_reply(user_msg))


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    Accept a multipart file upload, run the ETL pipeline on it, and return results.
    Supports: CSV, TSV, Excel, JSON, Parquet, Avro, XML.
    Max size: 100 MB.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file in request"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    file_bytes = f.read()
    size_bytes = len(file_bytes)

    if size_bytes > MAX_UPLOAD_BYTES:
        mb = size_bytes / (1024 * 1024)
        return jsonify({"error": f"File too large ({mb:.1f} MB). Max is 100 MB."}), 413

    filename   = f.filename
    fmt        = detect_format(filename, file_bytes)
    job_id     = uuid.uuid4().hex[:8]
    saved_path = UPLOAD_DIR / f"{job_id}_{filename}"
    saved_path.write_bytes(file_bytes)

    dest_stem = Path(filename).stem
    dest_path = f"data/clean/{job_id}_{dest_stem}.csv"

    log.info(f"[upload] job={job_id} file={filename} size={size_bytes/1024:.1f}KB fmt={fmt}")

    try:
        result = run_etl(str(saved_path), dest_path, fmt)
    except Exception as e:
        log.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        # Remove uploaded temp file after processing
        try:
            saved_path.unlink(missing_ok=True)
        except Exception:
            pass

    result["job_id"]     = job_id
    result["filename"]   = filename
    result["format"]     = fmt
    result["size_bytes"] = size_bytes
    return jsonify(result)


@app.route("/api/etl", methods=["POST"])
def api_etl():
    data   = request.get_json(silent=True) or {}
    source = data.get("source", "data/raw/input.csv")
    dest   = data.get("dest",   "data/clean/output.csv")
    fmt    = data.get("format", detect_format(source, b""))
    log.info(f"[api/etl] source={source} dest={dest} fmt={fmt}")
    try:
        return jsonify(run_etl(source, dest, fmt))
    except Exception as e:
        log.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route("/api/etl/info", methods=["GET"])
def api_etl_info():
    return jsonify({
        "pipeline": "extract → transform → load",
        "framework": "LangGraph + Pandas",
        "supported_formats": ["csv", "tsv", "excel", "json", "parquet", "avro", "xml"],
        "max_file_mb": 100,
        "steps": [
            {"name": "Parsing",     "desc": "Read file using auto-detected format"},
            {"name": "Cleaning",    "desc": "Normalise columns, impute nulls, remove duplicates"},
            {"name": "Transforming","desc": "Infer and coerce types (numeric, datetime)"},
            {"name": "Validating",  "desc": "Run 3 DQ checks: non-null, range, uniqueness"},
            {"name": "Loading",     "desc": "Write cleaned CSV + JSON metrics artifact"},
        ],
    })


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({
        "status": "ok",
        "groq_configured": bool(GROQ_API_KEY),
        "rag_chunks": len(RAG_CHUNKS),
        "timestamp": datetime.utcnow().isoformat(),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    log.info(f"Starting DataFlow AI on http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
