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

# LangChain imports
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_groq import ChatGroq

# ✅ FIXED IMPORTS (no chains module needed)
from langchain_core.prompts import PromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain

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


# ✅ RAG CHAIN (MODERN FIX)
def build_qa_chain(vs: Chroma):
    if not GROQ_API_KEY:
        raise ValueError("Set GROQ_API_KEY in .env")

    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name=GROQ_MODEL,
        temperature=0,
        max_tokens=1024,
    )

    retriever = vs.as_retriever(search_kwargs={"k": TOP_K})

    prompt = PromptTemplate.from_template(
        """Answer ONLY from the context.
If not found, say: I don't know based on the provided documents.

Context:
{context}

Question:
{input}
"""
    )

    doc_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, doc_chain)

    return rag_chain


# ROUTES
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    global vectorstore, qa_chain

    files = request.files.getlist("files")

    all_docs = []
    uploaded = []

    for f in files:
        path = UPLOAD_DIR / f.filename
        f.save(path)
        docs = load_document(str(path))
        all_docs.extend(docs)
        uploaded.append(f.filename)

    if not all_docs:
        return jsonify({"error": "No valid documents"}), 400

    chunks = split_documents(all_docs)
    vectorstore = build_vectorstore(chunks)
    qa_chain = build_qa_chain(vectorstore)

    return jsonify({
        "status": "success",
        "files": uploaded,
        "chunks": len(chunks)
    })


@app.route("/api/query", methods=["POST"])
def query():
    global qa_chain, vectorstore

    question = request.json.get("question", "").strip()

    if not question:
        return jsonify({"error": "No question"}), 400

    if qa_chain is None:
        vectorstore = load_existing_vectorstore()
        qa_chain = build_qa_chain(vectorstore)

    result = qa_chain.invoke({"input": question})

    answer = result.get("answer", "")

    sources = []
    for doc in result.get("context", []):
        meta = doc.metadata
        sources.append({
            "filename": meta.get("filename"),
            "type": meta.get("source_type"),
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
    global qa_chain, vectorstore

    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)

    CHROMA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(exist_ok=True)

    qa_chain = None
    vectorstore = None

    return jsonify({"status": "reset"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)