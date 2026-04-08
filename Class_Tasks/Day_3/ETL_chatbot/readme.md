# DataFlow AI — ETL Chatbot

A polished chatbot web app for data engineers. Ask questions about ETL pipelines,
Pandas, LangGraph, data quality, and observability. Run the embedded 3-step ETL example
directly from the UI.

---

## Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| Frontend  | Plain HTML + CSS + Vanilla JS       |
| Backend   | Python (Flask)                      |
| LLM       | Groq (`llama-3.1-8b-instant`)       |
| Fallback  | Ollama Mistral (local, free)        |
| ETL       | LangGraph + Pandas                  |
| RAG       | Keyword retrieval over `etl_rag.txt`|

---

## File Structure

```
.
├── app.py           # Flask backend, Groq/RAG/ETL logic
├── index.html       # Single-file frontend (dark moon UI)
├── etl_rag.txt      # Local knowledge base for RAG
├── requirements.txt
├── .env.example
└── data/
    ├── raw/         # Place input.csv here for ETL demo
    └── clean/       # ETL output written here
```

---

## Setup

### 1. Clone and install

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

Get a free Groq API key at https://console.groq.com.

### 3. (Optional) Local Mistral fallback

If Groq is unavailable, the app falls back to a locally-running Ollama Mistral instance.

```bash
# Install Ollama: https://ollama.com
ollama run mistral
```

Set in `.env`:
```
MISTRAL_FALLBACK_URL=http://localhost:11434/api/chat
MISTRAL_MODEL=mistral
```

### 4. Prepare ETL sample data (optional)

```bash
mkdir -p data/raw
# Place a CSV file at data/raw/input.csv
```

A minimal example CSV:
```csv
id,name,age,salary
1,Alice,30,70000
2,Bob,25,55000
3,,35,
1,Alice,30,70000
```

### 5. Run the app

```bash
python app.py
```

Open http://localhost:5000 in your browser.

---

## API Endpoints

| Method | Path          | Description                         |
|--------|---------------|-------------------------------------|
| GET    | `/`           | Serve the frontend                  |
| POST   | `/api/chat`   | Chat with the AI (`{"message": "…"}`)|
| POST   | `/api/etl`    | Run ETL pipeline (`{"source": "…", "dest": "…"}`)|
| GET    | `/api/etl/info` | Describe the ETL pipeline         |
| GET    | `/api/health` | Health check + config status        |

---

## Limitations

- RAG uses simple keyword overlap — not semantic vector search.
- ETL example is a demo on local CSV files; not a production ingestion system.
- Mistral fallback requires Ollama running locally.
- No authentication or rate limiting on API endpoints.
- LangGraph state carries full DataFrames in memory — not suitable for very large files.
