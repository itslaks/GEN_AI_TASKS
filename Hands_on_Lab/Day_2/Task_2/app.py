"""
FAQ RAG System — Production-Ready Backend
Flask + LangChain + ChromaDB + Groq API
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# LangChain
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

# Groq
from groq import Groq

# ─── Config ──────────────────────────────────────────────────────────────────

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
FAQ_FILE_PATH     = os.getenv("FAQ_FILE_PATH", "faq.txt")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME   = os.getenv("COLLECTION_NAME", "faq_collection")
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
GROQ_MODEL        = os.getenv("GROQ_MODEL", "llama3-8b-8192")
TOP_K             = int(os.getenv("TOP_K", "4"))
CHUNK_SIZE        = int(os.getenv("CHUNK_SIZE", "600"))
CHUNK_OVERLAP     = int(os.getenv("CHUNK_OVERLAP", "80"))

# ─── App ─────────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# Globals (initialized once)
vectorstore: Chroma | None = None
groq_client: Groq | None = None

# ─── Helpers ─────────────────────────────────────────────────────────────────

SAMPLE_FAQ = """
Q: What is your return policy?
A: We offer a 30-day hassle-free return policy. Items must be unused and in their original packaging. To initiate a return, contact support@example.com with your order number.

Q: How long does shipping take?
A: Standard shipping takes 5–7 business days. Express shipping (2–3 business days) is available at checkout for an additional fee. International orders may take 10–15 business days.

Q: Do you offer customer support on weekends?
A: Yes! Our support team is available Monday through Saturday, 9 AM–6 PM EST. You can reach us via live chat, email at support@example.com, or phone at 1-800-555-0199.

Q: How do I track my order?
A: Once your order ships, you'll receive a confirmation email with a tracking number. You can track your package on our website under "Order Status" or directly on the carrier's website.

Q: Can I change or cancel my order?
A: Orders can be modified or cancelled within 2 hours of placement. After that, the order enters processing and cannot be changed. Please contact support immediately if you need to make changes.

Q: What payment methods do you accept?
A: We accept Visa, Mastercard, American Express, PayPal, Apple Pay, and Google Pay. All transactions are encrypted and secured with SSL.

Q: Is my personal data safe?
A: Absolutely. We use industry-standard AES-256 encryption and never sell your personal data to third parties. Please review our full Privacy Policy at example.com/privacy.

Q: Do you offer discounts for bulk orders?
A: Yes! Orders of 10+ units qualify for a 15% discount, and orders of 50+ units qualify for 25% off. Contact our sales team at sales@example.com for a custom quote.

Q: What is your warranty policy?
A: All products come with a 1-year manufacturer's warranty covering defects in materials and workmanship. Accidental damage is not covered. Extended warranty plans are available at checkout.

Q: How do I reset my account password?
A: Click "Forgot Password" on the login page and enter your registered email. You'll receive a reset link within 5 minutes. If you don't see it, check your spam folder or contact support.

Q: Can I use multiple discount codes at once?
A: No, only one discount code can be applied per order. However, sale prices and loyalty rewards can be combined with a single promo code.

Q: Do you ship internationally?
A: Yes, we ship to over 50 countries. International shipping rates and delivery times vary by destination. Import duties and taxes are the buyer's responsibility.

Q: How do I become a loyalty member?
A: Sign up for free at example.com/loyalty. You'll earn 1 point per $1 spent. Points can be redeemed for discounts, free shipping, or exclusive products once you reach 100 points.

Q: What should I do if I receive a damaged item?
A: Take a photo of the damaged item and packaging, then email it to support@example.com within 48 hours of delivery. We'll arrange a free replacement or full refund immediately.

Q: Are your products eco-friendly?
A: We are committed to sustainability. Over 70% of our product line uses recycled or sustainably sourced materials. All packaging is 100% recyclable and plastic-free.
"""


def load_faq_document(file_path: str) -> List[Document]:
    """Load FAQ from file or fall back to built-in sample."""
    path = Path(file_path)
    if path.exists():
        log.info(f"Loading FAQ from: {file_path}")
        if file_path.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        else:
            loader = TextLoader(file_path, encoding="utf-8")
        return loader.load()
    else:
        log.warning(f"FAQ file not found at '{file_path}'. Using built-in sample FAQ.")
        return [Document(page_content=SAMPLE_FAQ, metadata={"source": "sample_faq"})]


def parse_qa_pairs(documents: List[Document]) -> List[Document]:
    """
    Parse Q&A pairs from text to preserve structure as individual chunks.
    Falls back to standard chunking if no Q/A pattern detected.
    """
    qa_pattern = re.compile(r"Q:\s*(.+?)\nA:\s*(.+?)(?=\nQ:|\Z)", re.DOTALL)
    structured_docs = []

    for doc in documents:
        matches = list(qa_pattern.finditer(doc.page_content))
        if matches:
            for i, m in enumerate(matches):
                question = m.group(1).strip()
                answer   = m.group(2).strip()
                chunk    = f"Question: {question}\nAnswer: {answer}"
                structured_docs.append(Document(
                    page_content=chunk,
                    metadata={
                        "source":   doc.metadata.get("source", "faq"),
                        "chunk_id": i,
                        "question": question[:200],
                        "type":     "qa_pair",
                    }
                ))
        else:
            structured_docs.append(doc)

    log.info(f"Parsed {len(structured_docs)} Q&A chunks.")
    return structured_docs


def chunk_documents(documents: List[Document]) -> List[Document]:
    """Split non-QA documents into semantic chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    # Only chunk docs that aren't already Q&A pairs
    qa_docs    = [d for d in documents if d.metadata.get("type") == "qa_pair"]
    plain_docs = [d for d in documents if d.metadata.get("type") != "qa_pair"]

    if plain_docs:
        split = splitter.split_documents(plain_docs)
        for i, d in enumerate(split):
            d.metadata.setdefault("chunk_id", i)
            d.metadata.setdefault("type", "chunk")
        qa_docs.extend(split)

    log.info(f"Total chunks ready for embedding: {len(qa_docs)}")
    return qa_docs


def build_vectorstore(chunks: List[Document]) -> Chroma:
    """Create or load persistent ChromaDB vectorstore."""
    log.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    persist_path = Path(CHROMA_PERSIST_DIR)

    if persist_path.exists() and any(persist_path.iterdir()):
        log.info("Loading existing ChromaDB collection...")
        vs = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
        )
    else:
        log.info("Creating new ChromaDB collection and embedding documents...")
        vs = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            collection_name=COLLECTION_NAME,
            persist_directory=CHROMA_PERSIST_DIR,
        )
        log.info(f"Stored {len(chunks)} chunks in ChromaDB.")

    return vs


def retrieve_context(query: str, vs: Chroma, top_k: int = TOP_K) -> List[Document]:
    """Retrieve top-k relevant chunks via similarity search."""
    retriever = vs.as_retriever(
        search_type="similarity",
        search_kwargs={"k": top_k},
    )
    results = retriever.invoke(query)
    log.info(f"Retrieved {len(results)} chunks for query: '{query[:60]}...'")
    return results


def build_prompt(query: str, context_docs: List[Document]) -> str:
    """Build a grounded, anti-hallucination prompt."""
    context_blocks = []
    for i, doc in enumerate(context_docs, 1):
        context_blocks.append(f"[Context {i}]\n{doc.page_content}")
    context_str = "\n\n".join(context_blocks)

    return f"""You are a precise and helpful FAQ assistant. Your ONLY job is to answer the user's question using the retrieved context below.

STRICT RULES:
1. Answer ONLY using information explicitly stated in the provided context.
2. Do NOT fabricate, infer, or guess anything not present in the context.
3. If the answer is not found in the context, respond EXACTLY: "I don't know based on the available FAQ information."
4. Be concise, factual, and professional.
5. Do not reference "Context 1", "Context 2" etc. in your answer — just answer naturally.

--- RETRIEVED CONTEXT ---
{context_str}
--- END OF CONTEXT ---

User Question: {query}

Answer:"""


def generate_answer(query: str, context_docs: List[Document], client: Groq) -> Dict[str, Any]:
    """Generate a grounded answer using Groq LLM."""
    prompt = build_prompt(query, context_docs)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,       # Low temperature = more faithful
        max_tokens=512,
        top_p=0.9,
    )

    answer = response.choices[0].message.content.strip()

    # Extract source snippets for transparency
    sources = []
    for doc in context_docs:
        snippet = doc.page_content[:150].replace("\n", " ") + "..."
        sources.append({
            "snippet": snippet,
            "metadata": doc.metadata,
        })

    return {
        "answer":  answer,
        "sources": sources,
        "model":   GROQ_MODEL,
        "chunks_retrieved": len(context_docs),
    }


# ─── Initialization ──────────────────────────────────────────────────────────

def initialize():
    """One-time startup: load data, build embeddings, connect to Groq."""
    global vectorstore, groq_client

    if not GROQ_API_KEY:
        raise EnvironmentError("GROQ_API_KEY is not set. Please check your .env file.")

    groq_client = Groq(api_key=GROQ_API_KEY)

    raw_docs = load_faq_document(FAQ_FILE_PATH)
    qa_docs  = parse_qa_pairs(raw_docs)
    chunks   = chunk_documents(qa_docs)
    vectorstore = build_vectorstore(chunks)

    log.info("✅ RAG system initialized and ready.")


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/ask", methods=["POST"])
def ask():
    """Main Q&A endpoint."""
    if vectorstore is None or groq_client is None:
        return jsonify({"error": "System not initialized."}), 503

    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Query cannot be empty."}), 400
    if len(query) > 1000:
        return jsonify({"error": "Query too long (max 1000 chars)."}), 400

    try:
        context_docs = retrieve_context(query, vectorstore)
        result = generate_answer(query, context_docs, groq_client)
        return jsonify(result)
    except Exception as e:
        log.error(f"Error processing query: {e}", exc_info=True)
        return jsonify({"error": "An internal error occurred. Please try again."}), 500


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "vectorstore": vectorstore is not None,
        "groq": groq_client is not None,
        "model": GROQ_MODEL,
        "embedding_model": EMBEDDING_MODEL,
    })


@app.route("/api/reload", methods=["POST"])
def reload_data():
    """Force reload and re-embed the FAQ document."""
    import shutil
    persist_path = Path(CHROMA_PERSIST_DIR)
    if persist_path.exists():
        shutil.rmtree(persist_path)
        log.info("Cleared existing ChromaDB store.")
    try:
        initialize()
        return jsonify({"status": "reloaded"})
    except Exception as e:
        log.error(f"Reload failed: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    initialize()
    port = int(os.getenv("PORT", 5000))
    log.info(f"🚀 Starting FAQ RAG server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
