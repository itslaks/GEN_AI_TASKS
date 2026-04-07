# 📄 PDF RAG — Semantic Search & Q&A over PDF Documents

> Index any PDF into ChromaDB, search it semantically, and ask questions answered by **Groq's free LLaMA 3.1 8B Instant** API — all 100% free.

---

## 🗂️ Project Structure

```
.
├── app.py              # Flask backend — PDF indexing, search, RAG Q&A
├── index.html          # Frontend UI (dark theme, zero dependencies)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── README.md           # This file
```

---

## 🚀 Quick Start

### 1. Clone / Download

```bash
git clone <your-repo>
cd pdf-rag
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ First run downloads the `all-MiniLM-L6-v2` embedding model (~80 MB). Subsequent runs use the cached model.

### 4. Set up your Groq API key

```bash
cp .env.example .env
```

Edit `.env` and add your free Groq API key from [console.groq.com](https://console.groq.com).

```env
GROQ_API_KEY=your_groq_api_key_here
```

### 5. Start the backend

```bash
python app.py
```

The API runs at `http://localhost:5000`.

### 6. Open the frontend

Open `index.html` directly in your browser (double-click it or use Live Server).

---

## 🔌 API Reference

| Method | Endpoint  | Description                                    |
|--------|-----------|------------------------------------------------|
| GET    | /health   | Health check + total indexed chunks            |
| POST   | /upload   | Upload & index a PDF (multipart/form-data)     |
| POST   | /search   | Semantic search — returns top-k chunks         |
| POST   | /ask      | RAG Q&A — returns AI answer + source chunks    |
| GET    | /stats    | Total chunks & list of indexed sources         |
| DELETE | /clear    | Wipe the entire ChromaDB collection            |

### POST /upload
```bash
curl -X POST http://localhost:5000/upload \
  -F "file=@manual.pdf"
```

### POST /search
```json
{ "query": "How do I reset the device?", "top_k": 5 }
```

### POST /ask
```json
{ "query": "What are the safety precautions?", "top_k": 5 }
```

---

## ⚙️ Architecture

```
PDF Upload
    │
    ▼
pypdf → Page Text Extraction
    │
    ▼
LangChain RecursiveCharacterTextSplitter
(800 chars / 150 overlap)
    │
    ▼
SentenceTransformer (all-MiniLM-L6-v2)  ← FREE, runs locally
    │
    ▼
ChromaDB (persistent, cosine similarity)
    │
    ├─── /search → Top-K Chunks + Similarity Scores
    │
    └─── /ask → Groq LLaMA 3.1 8B → Natural Language Answer
```

---

## 🔑 Free Resources Used

| Component      | Tool                          | Cost    |
|----------------|-------------------------------|---------|
| PDF Parsing    | pypdf                         | Free    |
| Text Chunking  | LangChain                     | Free    |
| Embeddings     | all-MiniLM-L6-v2 (local)      | Free    |
| Vector DB      | ChromaDB (local persistent)   | Free    |
| LLM / Q&A      | Groq API (LLaMA 3.1 8B)       | Free*   |

\* Groq free tier: 14,400 requests/day, 6,000 tokens/min

---

## 🛠️ Configuration

All settings in `.env`:

```env
GROQ_API_KEY=...          # Required
CHROMA_PERSIST_DIR=./chroma_db
COLLECTION_NAME=pdf_manual
UPLOAD_DIR=./uploads
```

---

## 📝 Notes

- Supports any text-based PDF (not scanned images without OCR)
- ChromaDB data persists in `./chroma_db` between restarts
- Uploaded PDFs are saved in `./uploads`
- Chunk size: 800 chars (~200 tokens), overlap: 150 chars
- Top-K defaults to 5 (configurable per request)
