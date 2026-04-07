# 🔍 FAQ RAG Assistant

A **production-ready Retrieval-Augmented Generation (RAG)** system that answers user questions strictly from a company FAQ document — no hallucinations, no guessing.

**Stack:** Python · Flask · LangChain · ChromaDB · HuggingFace Embeddings · Groq API (LLaMA 3)

---

## 📁 Project Structure

```
├── app.py            ← Flask backend: RAG pipeline (ingest → embed → retrieve → generate)
├── index.html        ← Frontend: Chat UI (served directly by Flask)
├── faq.txt           ← Your FAQ document (optional — sample FAQ built-in)
├── .env              ← Your API keys and config (copy from .env.example)
├── .env.example      ← Template for environment variables
├── chroma_db/        ← Auto-created: persistent ChromaDB vector store
└── README.md
```

---

## ⚡ Quick Start

### 1. Install Dependencies

```bash
pip install flask flask-cors python-dotenv \
            langchain langchain-community langchain-huggingface \
            chromadb sentence-transformers \
            groq pypdf
```

### 2. Set Up Environment

```bash
cp .env.example .env
```

Open `.env` and add your Groq API key:

```
GROQ_API_KEY=your_groq_api_key_here
```

Get a **free** Groq API key at [console.groq.com](https://console.groq.com) — no credit card required.

### 3. (Optional) Add Your FAQ Document

Place a `.txt` or `.pdf` FAQ file at the path specified by `FAQ_FILE_PATH` in your `.env` (default: `faq.txt`).

**TXT format example:**
```
Q: What is your return policy?
A: We offer a 30-day hassle-free return. Items must be unused...

Q: How long does shipping take?
A: Standard shipping takes 5–7 business days...
```

> If no file is found, the system automatically uses a built-in 15-question sample FAQ so you can test immediately.

### 4. Run the Server

```bash
python app.py
```

### 5. Open the UI

Visit [http://localhost:5000](http://localhost:5000) in your browser.

---

## 🏗️ How It Works

```
User Query
    │
    ▼
┌─────────────────────────────────┐
│  1. INGEST (on startup)         │
│  Load FAQ → Parse Q&A pairs →   │
│  Chunk → Embed (HuggingFace) →  │
│  Store in ChromaDB              │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  2. RETRIEVE                    │
│  Embed query → Similarity       │
│  search → Top-K chunks          │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│  3. GENERATE (Groq LLM)         │
│  Inject context → Grounded      │
│  prompt → LLaMA 3 answer        │
└─────────────────────────────────┘
    │
    ▼
Answer (with source citations)
```

---

## 🛡️ Anti-Hallucination Design

| Mechanism | Implementation |
|---|---|
| **Context-only prompt** | LLM is explicitly forbidden from using outside knowledge |
| **Low temperature** | `temperature=0.1` reduces creative deviation |
| **Explicit fallback** | Returns *"I don't know"* if context is insufficient |
| **Source transparency** | UI shows retrieved chunks alongside every answer |
| **Grounded retrieval** | Similarity search ensures only relevant FAQ sections are passed |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/`            | Serves the frontend UI |
| `POST` | `/api/ask`     | Submit a question `{"query": "..."}` |
| `GET`  | `/api/health`  | System health check |
| `POST` | `/api/reload`  | Clear ChromaDB and re-embed FAQ |

### Example API Call

```bash
curl -X POST http://localhost:5000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is your return policy?"}'
```

**Response:**
```json
{
  "answer": "We offer a 30-day hassle-free return policy. Items must be unused and in their original packaging. Contact support@example.com with your order number.",
  "sources": [
    {
      "snippet": "Question: What is your return policy? Answer: We offer a 30-day...",
      "metadata": { "chunk_id": 0, "type": "qa_pair" }
    }
  ],
  "model": "llama3-8b-8192",
  "chunks_retrieved": 4
}
```

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | *(required)* | Your Groq API key |
| `FAQ_FILE_PATH` | `faq.txt` | Path to FAQ document |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage location |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | HuggingFace embedding model |
| `GROQ_MODEL` | `llama3-8b-8192` | Groq LLM model |
| `TOP_K` | `4` | Retrieved chunks per query |
| `CHUNK_SIZE` | `600` | Max characters per chunk |
| `CHUNK_OVERLAP` | `80` | Overlap between chunks |
| `PORT` | `5000` | Flask server port |

---

## 🧪 Example Queries & Expected Behavior

| Query | Behavior |
|---|---|
| *"What is your return policy?"* | Returns specific return window and instructions |
| *"Do you ship to Japan?"* | Returns international shipping info |
| *"What is the meaning of life?"* | Returns *"I don't know based on the available FAQ information."* |
| *"Can I combine promo codes?"* | Returns single code limitation |

---

## 🔄 Updating the FAQ

1. Edit `faq.txt` (or your PDF)
2. Click **"⟳ Reload FAQ Data"** in the UI sidebar, or call `POST /api/reload`
3. ChromaDB is cleared and re-embedded automatically

---

## 📦 Requirements Summary

```
flask
flask-cors
python-dotenv
langchain
langchain-community
langchain-huggingface
chromadb
sentence-transformers
groq
pypdf
```

---

## 🪪 License

MIT — free to use, modify, and deploy.
