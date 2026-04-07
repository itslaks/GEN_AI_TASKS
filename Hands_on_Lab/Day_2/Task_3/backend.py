"""
Hybrid Search System Backend
Combines BM25 keyword search + ChromaDB vector similarity search
with metadata filtering using Groq LLaMA 3.1 8B embeddings via sentence-transformers
"""

import os
import json
import math
import re
import string
from collections import Counter
from typing import Any

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
CHROMA_PATH = "./chroma_store"
COLLECTION_NAME = "products"
EMBED_MODEL = "all-MiniLM-L6-v2"   # free, local, fast
GROQ_MODEL = "llama-3.1-8b-instant"

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# ─────────────────────────────────────────────
# Embedding Model (local, free)
# ─────────────────────────────────────────────
print("[INFO] Loading embedding model...")
embedder = SentenceTransformer(EMBED_MODEL)

# ─────────────────────────────────────────────
# ChromaDB (persistent)
# ─────────────────────────────────────────────
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"}
)

# ─────────────────────────────────────────────
# Groq Client
# ─────────────────────────────────────────────
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─────────────────────────────────────────────
# Sample Dataset
# ─────────────────────────────────────────────
SAMPLE_DOCUMENTS = [
    {"id": "p001", "text": "Sony WH-1000XM5 wireless noise cancelling headphones with 30 hour battery life and premium sound quality", "metadata": {"product_category": "electronics", "brand": "Sony", "price": 349.99, "rating": 4.8}},
    {"id": "p002", "text": "Apple AirPods Pro 2nd generation active noise cancellation spatial audio wireless earbuds", "metadata": {"product_category": "electronics", "brand": "Apple", "price": 249.00, "rating": 4.7}},
    {"id": "p003", "text": "Samsung 65 inch QLED 4K smart TV with Alexa built-in and crystal clear display", "metadata": {"product_category": "electronics", "brand": "Samsung", "price": 1299.99, "rating": 4.6}},
    {"id": "p004", "text": "Nike Air Max 270 running shoes lightweight breathable mesh comfortable everyday wear", "metadata": {"product_category": "footwear", "brand": "Nike", "price": 150.00, "rating": 4.5}},
    {"id": "p005", "text": "Adidas Ultraboost 22 running shoes energy return boost cushioning marathon training", "metadata": {"product_category": "footwear", "brand": "Adidas", "price": 190.00, "rating": 4.6}},
    {"id": "p006", "text": "The Ordinary Niacinamide 10% + Zinc 1% serum reduces blemishes pore appearance skin care", "metadata": {"product_category": "beauty", "brand": "The Ordinary", "price": 6.99, "rating": 4.7}},
    {"id": "p007", "text": "CeraVe Moisturizing Cream daily face body moisturizer dry skin ceramides hyaluronic acid", "metadata": {"product_category": "beauty", "brand": "CeraVe", "price": 16.99, "rating": 4.8}},
    {"id": "p008", "text": "Instant Pot Duo 7-in-1 electric pressure cooker slow cooker rice cooker steamer 6 quart", "metadata": {"product_category": "kitchen", "brand": "Instant Pot", "price": 89.99, "rating": 4.7}},
    {"id": "p009", "text": "Nespresso Vertuo Next coffee espresso machine with milk frother bundle barista quality", "metadata": {"product_category": "kitchen", "brand": "Nespresso", "price": 179.00, "rating": 4.5}},
    {"id": "p010", "text": "Logitech MX Master 3S wireless mouse ergonomic precision scroll wheel productivity", "metadata": {"product_category": "electronics", "brand": "Logitech", "price": 99.99, "rating": 4.7}},
    {"id": "p011", "text": "Kindle Paperwhite 11th generation waterproof e-reader 6.8 inch glare free display 8GB", "metadata": {"product_category": "electronics", "brand": "Amazon", "price": 139.99, "rating": 4.7}},
    {"id": "p012", "text": "LEGO Technic Lamborghini Sian FKP 37 42115 building kit collectible model car", "metadata": {"product_category": "toys", "brand": "LEGO", "price": 379.99, "rating": 4.9}},
    {"id": "p013", "text": "Hydro Flask 32 oz wide mouth water bottle stainless steel insulated keeps cold 24 hours", "metadata": {"product_category": "sports", "brand": "Hydro Flask", "price": 44.95, "rating": 4.8}},
    {"id": "p014", "text": "Vitamix 5200 blender professional grade variable speed smoothies soups nut butters", "metadata": {"product_category": "kitchen", "brand": "Vitamix", "price": 449.00, "rating": 4.8}},
    {"id": "p015", "text": "Bose QuietComfort 45 bluetooth wireless headphones noise cancelling over ear foldable", "metadata": {"product_category": "electronics", "brand": "Bose", "price": 329.00, "rating": 4.6}},
    {"id": "p016", "text": "Patagonia Men's Nano Puff Jacket lightweight packable wind resistant insulation", "metadata": {"product_category": "clothing", "brand": "Patagonia", "price": 259.00, "rating": 4.7}},
    {"id": "p017", "text": "Dyson V15 Detect cordless vacuum cleaner laser dust detection powerful suction", "metadata": {"product_category": "home", "brand": "Dyson", "price": 749.99, "rating": 4.6}},
    {"id": "p018", "text": "Theragun Prime percussive therapy device deep tissue massage muscle recovery", "metadata": {"product_category": "sports", "brand": "Therabody", "price": 299.00, "rating": 4.5}},
    {"id": "p019", "text": "Anker 737 power bank 24000mAh 140W fast charging MacBook laptop USB-C portable charger", "metadata": {"product_category": "electronics", "brand": "Anker", "price": 119.99, "rating": 4.6}},
    {"id": "p020", "text": "Stanley Quencher H2.0 FlowState tumbler 40oz stainless steel insulated cupholder compatible", "metadata": {"product_category": "sports", "brand": "Stanley", "price": 45.00, "rating": 4.7}},
]

# ─────────────────────────────────────────────
# BM25 Implementation (pure Python, no external lib)
# ─────────────────────────────────────────────
class BM25:
    """Okapi BM25 keyword scoring."""

    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.tokenized = [self._tokenize(doc) for doc in corpus]
        self.N = len(self.tokenized)
        self.avgdl = sum(len(d) for d in self.tokenized) / max(self.N, 1)
        self.df: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self._build_idf()

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = text.translate(str.maketrans("", "", string.punctuation))
        return text.split()

    def _build_idf(self):
        for tokens in self.tokenized:
            for term in set(tokens):
                self.df[term] = self.df.get(term, 0) + 1
        for term, freq in self.df.items():
            self.idf[term] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1)

    def score(self, query: str, doc_idx: int) -> float:
        query_terms = self._tokenize(query)
        doc_tokens = self.tokenized[doc_idx]
        tf_map = Counter(doc_tokens)
        dl = len(doc_tokens)
        score = 0.0
        for term in query_terms:
            if term not in self.idf:
                continue
            tf = tf_map.get(term, 0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            score += self.idf[term] * (numerator / denominator)
        return score

    def get_scores(self, query: str) -> list[float]:
        return [self.score(query, i) for i in range(self.N)]


# ─────────────────────────────────────────────
# Indexing
# ─────────────────────────────────────────────

def index_documents(documents: list[dict]):
    """Embed and store documents in ChromaDB."""
    existing = collection.get()["ids"]
    new_docs = [d for d in documents if d["id"] not in existing]
    if not new_docs:
        print("[INFO] All documents already indexed.")
        return

    texts = [d["text"] for d in new_docs]
    embeddings = embedder.encode(texts, show_progress_bar=True).tolist()

    collection.add(
        ids=[d["id"] for d in new_docs],
        documents=texts,
        embeddings=embeddings,
        metadatas=[d["metadata"] for d in new_docs],
    )
    print(f"[INFO] Indexed {len(new_docs)} documents into ChromaDB.")


# ─────────────────────────────────────────────
# Hybrid Search Core
# ─────────────────────────────────────────────

def _build_chroma_where(filters: dict) -> dict | None:
    """Convert flat filter dict to ChromaDB $and/$eq format."""
    if not filters:
        return None
    if len(filters) == 1:
        key, val = next(iter(filters.items()))
        return {key: {"$eq": val}}
    return {"$and": [{k: {"$eq": v}} for k, v in filters.items()]}


def query(
    text: str,
    top_k: int = 5,
    filters: dict | None = None,
    alpha: float = 0.5,
) -> list[dict]:
    """
    Hybrid search: BM25 + Vector similarity, merged by weighted score.

    Args:
        text:    Query string
        top_k:   Number of top results to return
        filters: Metadata filter dict e.g. {"product_category": "electronics"}
        alpha:   Weight for vector score (1-alpha for BM25). 0..1

    Returns:
        List of ranked result dicts with id, text, metadata, scores.
    """
    filters = filters or {}

    # ── 1. Fetch all candidate documents (apply metadata filter) ──────────
    where_clause = _build_chroma_where(filters)
    all_docs = collection.get(where=where_clause, include=["documents", "metadatas"])

    if not all_docs["ids"]:
        return []

    candidate_ids = all_docs["ids"]
    candidate_texts = all_docs["documents"]
    candidate_meta = all_docs["metadatas"]

    # ── 2. BM25 keyword scoring ────────────────────────────────────────────
    bm25 = BM25(candidate_texts)
    bm25_raw = bm25.get_scores(text)
    bm25_max = max(bm25_raw) if max(bm25_raw) > 0 else 1.0
    bm25_scores = [s / bm25_max for s in bm25_raw]   # normalise 0..1

    # ── 3. Vector similarity search (ChromaDB cosine) ─────────────────────
    query_embedding = embedder.encode([text]).tolist()
    vec_results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(len(candidate_ids), max(top_k * 3, 20)),
        where=where_clause,
        include=["documents", "metadatas", "distances"],
    )

    # Convert cosine distance → similarity score 0..1
    vec_score_map: dict[str, float] = {}
    for doc_id, dist in zip(vec_results["ids"][0], vec_results["distances"][0]):
        vec_score_map[doc_id] = 1.0 - dist   # cosine similarity

    # ── 4. Merge & rank ───────────────────────────────────────────────────
    merged: list[dict] = []
    for idx, doc_id in enumerate(candidate_ids):
        bm25_s = bm25_scores[idx]
        vec_s = vec_score_map.get(doc_id, 0.0)
        hybrid = alpha * vec_s + (1 - alpha) * bm25_s
        merged.append({
            "id": doc_id,
            "text": candidate_texts[idx],
            "metadata": candidate_meta[idx],
            "bm25_score": round(bm25_s, 4),
            "vector_score": round(vec_s, 4),
            "hybrid_score": round(hybrid, 4),
        })

    merged.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return merged[:top_k]


# ─────────────────────────────────────────────
# Groq AI Summary
# ─────────────────────────────────────────────

def generate_ai_summary(query_text: str, results: list[dict]) -> str:
    """Use Groq LLaMA to produce a short shopping assistant answer."""
    if not results:
        return "No products found matching your query."

    product_list = "\n".join(
        f"- {r['text'][:120]} (Category: {r['metadata'].get('product_category','?')}, "
        f"Brand: {r['metadata'].get('brand','?')}, Price: ${r['metadata'].get('price','?')})"
        for r in results[:5]
    )

    prompt = (
        f"You are a smart product search assistant. "
        f"A user searched for: \"{query_text}\"\n\n"
        f"Top matching products:\n{product_list}\n\n"
        f"In 2-3 sentences, summarise why these results match and highlight the best pick. "
        f"Be helpful and concise."
    )

    chat = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.7,
    )
    return chat.choices[0].message.content.strip()


# ─────────────────────────────────────────────
# Flask API Routes
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/search", methods=["POST"])
def api_search():
    body = request.get_json(force=True)
    text = body.get("query", "").strip()
    top_k = int(body.get("top_k", 5))
    filters = body.get("filters", {})
    alpha = float(body.get("alpha", 0.5))

    if not text:
        return jsonify({"error": "query is required"}), 400

    results = query(text, top_k=top_k, filters=filters, alpha=alpha)
    ai_summary = ""
    try:
        ai_summary = generate_ai_summary(text, results)
    except Exception as e:
        ai_summary = f"(AI summary unavailable: {e})"

    return jsonify({"results": results, "ai_summary": ai_summary, "count": len(results)})


@app.route("/api/categories", methods=["GET"])
def api_categories():
    all_meta = collection.get(include=["metadatas"])["metadatas"]
    cats = sorted({m.get("product_category", "unknown") for m in all_meta if m})
    return jsonify({"categories": cats})


@app.route("/api/ingest", methods=["POST"])
def api_ingest():
    body = request.get_json(force=True)
    docs = body.get("documents", [])
    if not docs:
        return jsonify({"error": "No documents provided"}), 400
    index_documents(docs)
    return jsonify({"indexed": len(docs)})


@app.route("/api/stats", methods=["GET"])
def api_stats():
    count = collection.count()
    all_meta = collection.get(include=["metadatas"])["metadatas"]
    cats = {}
    for m in all_meta:
        if m:
            c = m.get("product_category", "unknown")
            cats[c] = cats.get(c, 0) + 1
    return jsonify({"total_documents": count, "categories": cats})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": EMBED_MODEL, "groq_model": GROQ_MODEL})


# ─────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("[BOOT] Indexing sample documents...")
    index_documents(SAMPLE_DOCUMENTS)
    print("[BOOT] Starting Flask server on http://localhost:5000")
    app.run(debug=True, port=5000)
