# 🤖 Multi-Agent Research Pipeline

A 3-agent research pipeline powered by **LangGraph**, **Groq API**, and **ChromaDB**. Submit a topic and watch the Researcher → Writer → Editor agents collaboratively generate a polished, citation-backed report — all through a stunning glassmorphism UI.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-Backend-lightgrey?logo=flask)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-purple)
![Groq](https://img.shields.io/badge/Groq-LLM-orange)
![ChromaDB](https://img.shields.io/badge/ChromaDB-VectorDB-green)

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **3-Agent pipeline** | Researcher → Writer → Editor via LangGraph state graph |
| **Vector retrieval** | ChromaDB stores & retrieves research chunks per run |
| **Markdown reports** | Final output rendered with full markdown (headers, bold, lists, code) |
| **Tabbed results** | Switch between Final Report, Draft, and Citations |
| **Research notes** | Sidebar shows each research point with its source |
| **Live pipeline tracker** | Animated agent nodes with connectors & timing labels |
| **Toast notifications** | Success / error feedback with auto-dismiss |
| **Health indicator** | Header badge shows server & LLM connectivity status |
| **Copy & download** | One-click clipboard copy or `.md` file download |
| **Collapsible logs** | Colour-coded execution logs with timestamps |
| **Rate limiting** | IP-based rate limiter with `Retry-After` headers |
| **Input validation** | Server-side schema validation + client-side checks |
| **Fallback mode** | Works without API key (returns placeholder content) |
| **Responsive** | Mobile-first grid layout |

---

## 🏗️ Architecture

```
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│   Researcher   │────▶│     Writer     │────▶│     Editor     │
│     Agent      │     │     Agent      │     │     Agent      │
└───────┬────────┘     └───────┬────────┘     └───────┬────────┘
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               │
                      ┌────────▼────────┐
                      │    ChromaDB     │
                      │  (Vector Store) │
                      └─────────────────┘
```

### Agent Workflow

1. **🔍 Researcher Agent**
   - Prompts the LLM for 5 key research points with sources
   - Parses `POINT:` / `SOURCE:` formatted responses
   - Stores document chunks + metadata in a per-run ChromaDB collection
   - Deduplicates citations

2. **✍️ Writer Agent**
   - Queries ChromaDB for the top-5 most relevant chunks
   - Generates a markdown-formatted draft report
   - Adapts tone/length based on **audience** and **length** settings
   - Includes inline `[Source: URL]` citations

3. **✨ Editor Agent**
   - Polishes grammar, structure, and flow
   - Ensures claims map to available citations
   - Outputs publication-ready markdown

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Groq API key** — free tier at [console.groq.com](https://console.groq.com)

### Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env (or edit the existing one)
#    Add your GROQ_API_KEY
cp .env.example .env   # if .env doesn't exist yet

# 3. Start the server
python app.py

# 4. Open in browser
#    http://localhost:5000
```

> **Note:** The app uses `python-dotenv` to automatically load `.env` at startup — no manual `export` required.

---

## 🔐 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | **Yes** | — | Groq API key for LLM calls |
| `FLASK_SECRET_KEY` | No | random | Session secret (auto-generated if missing) |
| `ALLOWED_ORIGINS` | No | `*` | CORS allowed origins |
| `RATE_LIMIT_IP` | No | `15` | Max requests per IP per window |
| `RATE_LIMIT_WINDOW` | No | `60` | Rate-limit window in seconds |
| `PORT` | No | `5000` | Server port |
| `DEBUG` | No | `false` | Enable Flask debug mode |

---

## 📊 API Endpoints

### `POST /api/run`

Execute the full 3-agent research pipeline.

**Request body:**
```json
{
  "query": "Impact of AI on modern healthcare",
  "audience": "general",
  "length": "medium"
}
```

**Success response (200):**
```json
{
  "run_id": "uuid",
  "status": "completed",
  "final_report": "# Report Title\n\nMarkdown content…",
  "draft_report": "# Draft\n\n…",
  "research_notes": [
    { "content": "Key finding…", "source": "https://…" }
  ],
  "citations": ["https://…"],
  "logs": [
    { "timestamp": "…", "node": "researcher", "message": "…" }
  ]
}
```

**Error codes:** `400` (validation) · `429` (rate limit) · `500` (server) · `503` (busy)

---

### `GET /api/status/<run_id>`

Get status and logs for a specific run.

---

### `GET /api/health`

Health check — returns LLM availability and key status.

```json
{
  "status": "healthy",
  "llm_available": true,
  "groq_key_set": true,
  "timestamp": "2026-04-08T07:30:00"
}
```

---

### `GET /api/history`

Returns last 20 completed runs (run_id, query, status).

---

## 🎨 Frontend Design

The UI is a **single-file** `index.html` with no build step.

### Visual Design
- **Dark glassmorphism** theme with frosted-glass cards
- **Animated background** — subtle grid + floating gradient orbs
- **Inter + JetBrains Mono** typography from Google Fonts
- **Micro-animations** — pulse effects, shimmer buttons, smooth transitions
- **Purple / cyan / green** accent palette with coordinated dim variants

### Interactive Elements
- **Pipeline tracker** — animated circles + connector bars showing agent progress
- **Tabbed report viewer** — Final Report / Draft / Citations tabs
- **Research notes sidebar** — collapsible panel with source links
- **Execution logs** — colour-coded by agent (researcher=cyan, writer=pink, editor=green)
- **Toast notifications** — slide-in toasts for success/error/info
- **Health badge** — real-time server connectivity indicator
- **Copy & download** — one-click report export (clipboard or `.md` file)
- **Character counter** — live count on the query input

### Markdown Rendering
The final report is rendered as rich HTML using [marked.js](https://marked.js.org/), supporting headings, bold, lists, blockquotes, code, and links.

---

## 📁 Project Structure

```
Task_4/
├── app.py              # Flask backend — agents, LangGraph, ChromaDB, API routes
├── index.html          # Single-file frontend — glassmorphism UI
├── requirements.txt    # Python dependencies
├── .env                # Environment config (GROQ_API_KEY etc.)
├── README.md           # This file
└── chroma_db/          # ChromaDB persistent storage (auto-created)
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| `GROQ_API_KEY not set` | Add your key to `.env` → `GROQ_API_KEY=gsk_…` |
| Header shows "Fallback Mode" | The `.env` key is missing or invalid |
| `Rate limit exceeded` | Wait, or increase `RATE_LIMIT_IP` in `.env` |
| `ChromaDB error` | Delete `chroma_db/` folder and restart |
| `Port already in use` | Set `PORT=8080` in `.env` or kill the old process |
| Query rejected | Queries must be 3–500 chars; angle brackets & backticks are blocked |

---

## 🧪 Fallback Mode

When `GROQ_API_KEY` is not set, the app runs in **fallback mode**:

- Agents return placeholder content (no API calls)
- Useful for testing the UI without using API quota
- Health badge shows "Fallback Mode (No API Key)"

```bash
# Test fallback: remove or comment out GROQ_API_KEY in .env
python app.py
```

---

## 🛡️ Production Deployment

```bash
# Install a production WSGI server
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Recommended:
# - Set ALLOWED_ORIGINS to your domain
# - Set DEBUG=false
# - Use HTTPS via reverse proxy (nginx/Caddy)
# - Rotate API keys periodically
```

---

## 🔗 Resources

- [Groq API Docs](https://console.groq.com/docs)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [ChromaDB Docs](https://docs.trychroma.com/)
- [Flask Docs](https://flask.palletsprojects.com/)
- [marked.js](https://marked.js.org/)

---

**Built with ❤️ using LangGraph + Groq + ChromaDB**
