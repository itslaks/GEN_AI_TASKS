# ⬡ NEXUS RAG — Multi-Document Intelligence System

A production-ready Retrieval-Augmented Generation (RAG) system with a stunning dark-theme UI.
Ingest **PDF, CSV, and TXT** files, index them into a persistent ChromaDB vector store, and query
them via a Groq-powered LLM — all with zero hallucination, zero paid APIs beyond Groq's generous free tier.

---

## Architecture

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  index.html │────▶│     Flask (app.py)   │────▶│  ChromaDB (disk)│
│  Dark UI    │     │  /api/upload         │     │  chroma_db/     │
│             │     │  /api/query          │     └─────────────────┘
│             │     │  /api/status         │             │
│             │     │  /api/reset          │             ▼
└─────────────┘     └──────────────────────┘     ┌─────────────────┐
                             │                   │  HuggingFace    │
                             ▼                   │  MiniLM-L6-v2   │
                    ┌──────────────────┐         │  Embeddings     │
                    │   Groq LLaMA     │         └─────────────────┘
                    │ 3.1 8B Instant   │
                    └──────────────────┘
```

**Document flow:**
1. Files uploaded → LangChain loaders (PyPDFLoader / CSVLoader / TextLoader)
2. Documents chunked (600 tokens, 100 overlap) with RecursiveCharacterTextSplitter
3. Chunks embedded with `all-MiniLM-L6-v2` (free, local, no API needed)
4. Embeddings stored in ChromaDB (persistent on disk)
5. Query → similarity search (top-5 chunks) → LLaMA 3.1 via Groq → grounded answer

---

## Quick Start

### 1. Prerequisites

- Python 3.10
- A free Groq API key → https://console.groq.com

### 2. Clone / place files

```
nexus-rag/
├── app.py
├── index.html
├── requirements.txt
├── .env.example
└── README.md
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note for CPU-only machines:** PyTorch will be installed automatically.
> If you want to skip GPU packages explicitly:
> `pip install torch --index-url https://download.pytorch.org/whl/cpu`

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env and set your GROQ_API_KEY
```

### 5. Run the server

```bash
python app.py
```

Open your browser at **http://localhost:5000**

---

## Usage

### Via the Web UI

1. **Upload** — Drag & drop or click to select PDF, CSV, or TXT files
2. **Index** — Click "⚡ Index Documents" and wait for chunking + embedding
3. **Query** — Type any question in the chat box and press Enter

### Via curl (API)

**Upload files:**
```bash
curl -X POST http://localhost:5000/api/upload \
  -F "files=@report.pdf" \
  -F "files=@data.csv" \
  -F "files=@notes.txt"
```

**Query:**
```bash
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the main conclusions in the report?"}'
```

**Check status:**
```bash
curl http://localhost:5000/api/status
```

**Reset everything:**
```bash
curl -X POST http://localhost:5000/api/reset
```

---

## Example Queries

| Document Type | Example Question |
|---|---|
| PDF report | "What are the key findings in chapter 3?" |
| CSV dataset | "What is the average value in the revenue column?" |
| TXT notes   | "Summarize the action items mentioned" |
| Mixed       | "What common themes appear across all documents?" |

---

## Anti-Hallucination

The system is designed to **never fabricate** information:

- Temperature set to `0.0` for deterministic, factual outputs
- Prompt explicitly instructs the LLM to only use retrieved context
- If the answer isn't in the documents, the system responds:
  > *"I don't know based on the provided documents."*
- Every answer includes **source attribution** (filename, type, page/row, snippet)

---

## Configuration

Edit these constants in `app.py` or override via `.env`:

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Your Groq API key (required) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq model name |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace embedding model |
| `CHUNK_SIZE` | `600` | Tokens per chunk |
| `CHUNK_OVERLAP` | `100` | Overlap between chunks |
| `TOP_K` | `5` | Number of chunks retrieved per query |
| `CHROMA_DIR` | `chroma_db/` | ChromaDB persistence directory |
| `UPLOAD_DIR` | `uploads/` | Uploaded files directory |

---

## Supported File Types

| Extension | Loader | Metadata Preserved |
|---|---|---|
| `.pdf` | `PyPDFLoader` | filename, page number |
| `.csv` | `CSVLoader` | filename, row index |
| `.txt` / `.md` | `TextLoader` | filename |

---

## Free Resources Used

| Component | Tool | Cost |
|---|---|---|
| LLM | Groq (LLaMA 3.1 8B) | Free tier |
| Embeddings | HuggingFace MiniLM | Free, local |
| Vector DB | ChromaDB | Free, local |
| Framework | LangChain | Open source |
| Backend | Flask | Open source |

---

## Troubleshooting

**`GROQ_API_KEY` not set error**
→ Make sure `.env` exists with a valid key, or `export GROQ_API_KEY=your_key`

**Slow first query**
→ MiniLM model downloads on first run (~90MB). Subsequent runs use cache.

**ChromaDB version conflict**
→ Run `pip install chromadb --upgrade`

**Port already in use**
→ `python app.py` uses port 5000. Change with: `app.run(port=5001)`
