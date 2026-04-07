# NEXUS — Hybrid Search Engine

A production-grade hybrid search system combining **BM25 keyword retrieval** + **ChromaDB vector similarity search** with **metadata filtering** and an **AI-powered summary** via Groq LLaMA 3.1 8B.

---

## Architecture

```
Query
  ├── BM25 Scorer      (pure Python, no external API)
  ├── ChromaDB Vector  (sentence-transformers all-MiniLM-L6-v2, local)
  └── Groq LLaMA 3.1   (AI summary, FREE tier available)
          ↓
    Weighted Merge (α · vec + (1-α) · bm25)
          ↓
    Ranked Results + Metadata Filter
```

---

## Files

| File | Purpose |
|------|---------|
| `backend.py` | Flask API — BM25, ChromaDB, Groq integration |
| `index.html` | Dark-theme frontend — single file |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |
| `README.md` | This file |

---

## Quick Start

### 1. Get a FREE Groq API Key
Visit https://console.groq.com → Sign up → Create API Key (free tier).

### 2. Setup Environment
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Backend
```bash
python backend.py
```
First run downloads the embedding model (~90MB, one-time). Then indexes 20 sample products.

### 5. Open Frontend
Open `index.html` in your browser. (No build step needed.)

---

## API Reference

### `POST /api/search`
```json
{
  "query": "wireless headphones",
  "top_k": 5,
  "filters": { "product_category": "electronics" },
  "alpha": 0.5
}
```
- `alpha`: 0 = pure BM25, 1 = pure vector, 0.5 = balanced

**Response:**
```json
{
  "results": [
    {
      "id": "p001",
      "text": "Sony WH-1000XM5...",
      "metadata": { "product_category": "electronics", "brand": "Sony", ... },
      "bm25_score": 0.8123,
      "vector_score": 0.9201,
      "hybrid_score": 0.8662
    }
  ],
  "ai_summary": "These results match your query because...",
  "count": 5
}
```

### `GET /api/stats`
Returns total document count and per-category breakdown.

### `GET /api/categories`
Returns list of all available categories.

### `POST /api/ingest`
Add custom documents:
```json
{
  "documents": [
    {
      "id": "custom001",
      "text": "Your product description here",
      "metadata": { "product_category": "electronics", "brand": "ACME", "price": 99.99, "rating": 4.5 }
    }
  ]
}
```

---

## How Hybrid Search Works

1. **Candidate Retrieval**: All documents matching the metadata filter are fetched from ChromaDB.
2. **BM25 Scoring**: Each candidate is scored against the query using Okapi BM25 (term frequency + inverse document frequency). Scores are normalised to [0, 1].
3. **Vector Scoring**: ChromaDB performs cosine similarity search using `all-MiniLM-L6-v2` embeddings. Cosine distance is converted to similarity: `score = 1 - distance`.
4. **Weighted Fusion**: `hybrid = α × vector + (1-α) × bm25`
5. **Ranking**: Results sorted by hybrid score descending.
6. **AI Summary**: Top-5 results are sent to Groq LLaMA 3.1 8B for a natural-language explanation.

---

## Sample Queries to Try

```
"noise cancelling headphones"           → electronics
"running shoes cushioning"             → footwear
"skin care moisturizer ceramides"      → beauty
"coffee espresso machine"              → kitchen
"wireless mouse ergonomic"             → electronics (filtered)
"fast charging portable battery"       → electronics
```

---

## Dependencies

- `flask` + `flask-cors` — REST API server
- `chromadb` — Vector database (local, persistent)
- `sentence-transformers` — Local embedding model (free, no API key)
- `groq` — LLaMA 3.1 8B inference (free tier)
- `python-dotenv` — Environment management

**No OpenAI. No paid APIs required.**
