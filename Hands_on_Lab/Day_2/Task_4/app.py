"""
Multi-Document RAG System — Backend (Flask + LangChain + ChromaDB + Groq)
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# LangChain imports
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

# CONFIG
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
CHROMA_DIR = Path("chroma_db")
UPLOAD_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GROQ_MODEL = "llama-3.1-8b-instant"

CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
TOP_K = 5
COLLECTION_NAME = "rag_collection"

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

embeddings = None
vectorstore = None
qa_chain = None
indexed_file_count = 0


# EMBEDDINGS
def get_embeddings():
    global embeddings
    if embeddings is None:
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return embeddings


# LOAD DOCUMENT
def load_document(filepath: str) -> List[Document]:
    path = Path(filepath)
    ext = path.suffix.lower()
    filename = path.name

    docs = []

    if ext == ".pdf":
        raw = PyPDFLoader(str(path)).load()
        for d in raw:
            d.metadata.update({"filename": filename, "source_type": "pdf"})
        docs = raw

    elif ext == ".csv":
        raw = CSVLoader(str(path)).load()
        for i, d in enumerate(raw):
            d.metadata.update({"filename": filename, "source_type": "csv", "row": i})
        docs = raw

    elif ext in (".txt", ".md"):
        raw = TextLoader(str(path)).load()
        for d in raw:
            d.metadata.update({"filename": filename, "source_type": "text"})
        docs = raw

    return docs


# SPLIT
def split_documents(docs: List[Document]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_documents(docs)


# VECTOR STORE
def build_vectorstore(chunks: List[Document]) -> Chroma:
    vs = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )
    vs.add_documents(chunks)
    vs.persist()
    return vs


def load_existing_vectorstore():
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def get_indexed_chunk_count(vs: Chroma) -> int:
    try:
        collection = vs._collection
        data = collection.get(include=[])
        return len(data.get("ids", []))
    except Exception:
        return 0


def get_llm():
    if not GROQ_API_KEY:
        raise ValueError("Set GROQ_API_KEY in .env")
    return ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name=GROQ_MODEL,
        temperature=0,
        max_tokens=1024,
    )


def answer_with_rag(vs: Chroma, question: str) -> Dict[str, Any]:
    retriever = vs.as_retriever(search_kwargs={"k": TOP_K})
    context_docs = retriever.invoke(question)
    context_text = "\n\n".join(doc.page_content for doc in context_docs)

    prompt = PromptTemplate.from_template(
        """Answer ONLY from the context.
If not found, say: I don't know based on the provided documents.

Context:
{context}

Question:
{input}
"""
    )

    llm = get_llm()
    prompt_text = prompt.format(context=context_text, input=question)
    response = llm.invoke(prompt_text)
    answer = getattr(response, "content", str(response))
    return {"answer": answer, "context": context_docs}


# ROUTES
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/favicon.ico")
def favicon():
    return ("", 204)


@app.route("/api/status", methods=["GET"])
def status():
    global vectorstore, indexed_file_count
    try:
        if vectorstore is None:
            vectorstore = load_existing_vectorstore()
        chunks = get_indexed_chunk_count(vectorstore)
        return jsonify({
            "ready": chunks > 0,
            "indexed_chunks": chunks,
            "indexed_files": indexed_file_count,
        })
    except Exception:
        return jsonify({
            "ready": False,
            "indexed_chunks": 0,
            "indexed_files": indexed_file_count,
        })


@app.route("/api/upload", methods=["POST"])
def upload():
    global vectorstore, qa_chain, indexed_file_count

    files = request.files.getlist("files")

    all_docs = []
    uploaded = []

    for f in files:
        if not f.filename:
            continue
        filename = secure_filename(f.filename)
        if not filename:
            continue
        path = UPLOAD_DIR / filename
        f.save(path)
        try:
            docs = load_document(str(path))
        except Exception as e:
            logger.exception("Failed to load %s: %s", filename, e)
            continue
        all_docs.extend(docs)
        if docs:
            uploaded.append(filename)

    if not all_docs:
        return jsonify({"error": "No valid documents"}), 400

    chunks = split_documents(all_docs)
    vectorstore = build_vectorstore(chunks)
    qa_chain = True
    indexed_file_count = len(uploaded)

    return jsonify({
        "status": "success",
        "files": uploaded,
        "chunks": len(chunks),
        "chunks_indexed": len(chunks),
    })


@app.route("/api/query", methods=["POST"])
def query():
    global qa_chain, vectorstore

    payload = request.get_json(silent=True) or {}
    question = payload.get("question", "").strip()

    if not question:
        return jsonify({"error": "No question"}), 400

    if qa_chain is None:
        vectorstore = load_existing_vectorstore()
        qa_chain = True

    result = answer_with_rag(vectorstore, question)

    answer = result.get("answer", "")

    sources = []
    for doc in result.get("context", []):
        meta = doc.metadata
        sources.append({
            "filename": meta.get("filename"),
            "type": meta.get("source_type"),
            "source_type": meta.get("source_type"),
            "page": meta.get("page", meta.get("row")),
            "snippet": doc.page_content[:150]
        })

    return jsonify({
        "question": question,
        "answer": answer,
        "sources": sources
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    import shutil
    global qa_chain, vectorstore, indexed_file_count

    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)

    CHROMA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(exist_ok=True)

    qa_chain = None
    vectorstore = None
    indexed_file_count = 0

    return jsonify({"status": "reset"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)