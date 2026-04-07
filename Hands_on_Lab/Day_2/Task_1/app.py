"""
PDF RAG Backend — ChromaDB + Groq (LLaMA 3.1 8B Instant)
==========================================================
Provides a Flask API for:
  - Uploading & indexing PDFs into ChromaDB
  - Semantic search over indexed chunks
  - RAG-based Q&A using Groq's free API
"""

import os
import uuid
import json
import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from groq import Groq
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

# ── Config ─────────────────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME    = os.getenv("COLLECTION_NAME", "pdf_manual")
UPLOAD_DIR         = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Chunk settings
CHUNK_SIZE    = 800   # ~tokens (chars ÷ 4)
CHUNK_OVERLAP = 150
TOP_K         = 5

# ── Clients ────────────────────────────────────────────────────────────────────
groq_client = Groq(api_key=GROQ_API_KEY)

# Use ChromaDB's built-in sentence-transformers embedding (free, local)
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=ef,
    metadata={"hnsw:space": "cosine"},
)

# ── Flask App ──────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder=".", static_folder=".", static_url_path="")
CORS(app)


# ── PDF Processing ─────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Extract text page-by-page from a PDF.
    Returns list of {page_num, text} dicts, skipping blank pages.
    """
    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
            text = text.strip()
            if not text:
                log.warning(f"Page {i} is empty — skipping.")
                continue
            pages.append({"page_num": i, "text": text})
        except Exception as exc:
            log.error(f"Failed to extract page {i}: {exc}")
    log.info(f"Extracted {len(pages)} non-empty pages.")
    return pages


def chunk_pages(pages: list[dict]) -> list[dict]:
    """
    Split page text into overlapping chunks using LangChain's splitter.
    Returns list of {chunk_id, page_num, text} dicts.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = []
    for page in pages:
        splits = splitter.split_text(page["text"])
        for j, split in enumerate(splits):
            chunk_id = f"p{page['page_num']}_c{j}"
            chunks.append({
                "chunk_id": chunk_id,
                "page_num": page["page_num"],
                "text": split.strip(),
            })
    log.info(f"Created {len(chunks)} chunks.")
    return chunks


def index_chunks(chunks: list[dict], source_name: str) -> int:
    """
    Upsert chunks into ChromaDB collection.
    Returns number of chunks indexed.
    """
    if not chunks:
        return 0

    ids       = [c["chunk_id"] for c in chunks]
    documents = [c["text"]     for c in chunks]
    metadatas = [
        {"page_num": c["page_num"], "source": source_name, "chunk_id": c["chunk_id"]}
        for c in chunks
    ]

    # Batch upsert (ChromaDB handles duplicates gracefully)
    BATCH = 100
    for start in range(0, len(chunks), BATCH):
        collection.upsert(
            ids=ids[start:start+BATCH],
            documents=documents[start:start+BATCH],
            metadatas=metadatas[start:start+BATCH],
        )
    log.info(f"Indexed {len(chunks)} chunks from '{source_name}'.")
    return len(chunks)


# ── Retrieval ──────────────────────────────────────────────────────────────────

def semantic_search(query: str, top_k: int = TOP_K, source: Optional[str] = None) -> list[dict]:
    """
    Search ChromaDB for top-k chunks most relevant to query.
    Optionally filter by source document name.
    """
    where = {"source": source} if source else None
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "text":       doc,
            "metadata":   meta,
            "similarity": round(1 - dist, 4),   # cosine → similarity
        })
    return hits


# ── RAG Q&A ────────────────────────────────────────────────────────────────────

def rag_answer(query: str, top_k: int = TOP_K, source: Optional[str] = None) -> dict:
    """
    Retrieve relevant chunks, then ask Groq LLaMA to answer.
    """
    hits = semantic_search(query, top_k=top_k, source=source)
    if not hits:
        return {"answer": "No relevant content found in the indexed documents.", "sources": []}

    context = "\n\n---\n\n".join(
        f"[Page {h['metadata']['page_num']}]\n{h['text']}" for h in hits
    )
    system_prompt = (
        "You are a precise document assistant. Answer the user's question "
        "strictly based on the provided document excerpts. "
        "If the answer isn't in the excerpts, say so clearly. "
        "Be concise, accurate, and cite page numbers when relevant."
    )
    user_prompt = f"Document excerpts:\n\n{context}\n\nQuestion: {query}"

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    answer = response.choices[0].message.content.strip()
    return {"answer": answer, "sources": hits}


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health", methods=["GET"])
def health():
    count = collection.count()
    return jsonify({"status": "ok", "indexed_chunks": count})


@app.route("/upload", methods=["POST"])
def upload_pdf():
    """Upload and index a PDF."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted"}), 400

    save_path = UPLOAD_DIR / file.filename
    file.save(str(save_path))
    log.info(f"Saved upload: {save_path}")

    try:
        pages  = extract_text_from_pdf(str(save_path))
        chunks = chunk_pages(pages)
        count  = index_chunks(chunks, source_name=file.filename)
        return jsonify({
            "message":       "PDF indexed successfully",
            "filename":      file.filename,
            "pages_parsed":  len(pages),
            "chunks_indexed": count,
        })
    except Exception as exc:
        log.error(f"Indexing failed: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/search", methods=["POST"])
def search():
    """Semantic search — returns top-k chunks with similarity scores."""
    body   = request.json or {}
    query  = body.get("query", "").strip()
    top_k  = int(body.get("top_k", TOP_K))
    source = body.get("source")

    if not query:
        return jsonify({"error": "Query is required"}), 400

    try:
        hits = semantic_search(query, top_k=top_k, source=source)
        return jsonify({"query": query, "results": hits})
    except Exception as exc:
        log.error(f"Search failed: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/ask", methods=["POST"])
def ask():
    """RAG Q&A — retrieve context, answer with Groq LLaMA."""
    body   = request.json or {}
    query  = body.get("query", "").strip()
    top_k  = int(body.get("top_k", TOP_K))
    source = body.get("source")

    if not query:
        return jsonify({"error": "Query is required"}), 400

    try:
        result = rag_answer(query, top_k=top_k, source=source)
        return jsonify(result)
    except Exception as exc:
        log.error(f"RAG failed: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/stats", methods=["GET"])
def stats():
    """Return collection statistics."""
    count = collection.count()
    # Get distinct sources from metadata
    try:
        results = collection.get(include=["metadatas"], limit=10000)
        sources = list({m["source"] for m in results["metadatas"]})
    except Exception:
        sources = []
    return jsonify({"total_chunks": count, "sources": sources})


@app.route("/clear", methods=["DELETE"])
def clear():
    """Delete all documents from the collection."""
    global collection
    chroma_client.delete_collection(COLLECTION_NAME)
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    return jsonify({"message": "Collection cleared."})


# ── Entry Point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Starting PDF RAG API on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
