# ⚡ NeuralGuard — Human-in-the-Loop Content Moderation

A content moderation system with **human-in-the-loop (HITL) approval** for flagged content, powered by **LangGraph** state-graph orchestration, **Groq LLM** analysis, and a **Flask** approval UI.

Content is scored heuristically, enriched by LLM analysis (Groq `llama-3.1-8b-instant`), then either auto-resolved or paused at a **human review gate** where a moderator approves or denies via the interactive UI.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **3-node LangGraph workflow** | Ingest → Auto-Moderate → (Human Review) → Finalize |
| **HITL pause/resume** | `interrupt_before` + `MemorySaver` checkpointer freezes state at the review gate |
| **Rule-based scoring** | 7 toxicity categories (hate, violence, spam, profanity, explicit, threat, self-harm) |
| **LLM enrichment** | Groq `llama-3.1-8b-instant` explains *why* content is flagged; Ollama Mistral fallback |
| **Approve / Deny UI** | Moderator reviews flagged items, adds comments, and decides |
| **Audit trail** | Every node appends a timestamped event — viewable per-item in a modal |
| **Dashboard stats** | Pending, auto-approved, auto-denied, human-reviewed counters |
| **Quick samples** | One-click test buttons: Safe, Borderline, Toxic, Spam, Threat |
| **Dark glassmorphism UI** | Animated grid, floating orbs, Syne + JetBrains Mono typography |
| **Toast notifications** | Real-time feedback on submit / approve / deny actions |
| **CORS enabled** | API accessible cross-origin for integration scenarios |
| **No paid services** | Groq free tier + optional local Ollama — no OpenAI required |

---

## 🏗️ Architecture

```
[Ingest] → [Auto-Moderate] → [Route]
                                 ├── score < 0.30 → [Finalize: auto-approve]
                                 ├── score >= 0.70 → [Finalize: auto-deny]
                                 └── 0.30 ≤ score < 0.70 → [Human Review Gate]
                                                                  ↓ (pause — interrupt_before)
                                                          Human approves/denies via UI
                                                                  ↓ (resume — graph.stream)
                                                          [Finalize: human decision]
```

### Scoring Thresholds

| Score Range     | Decision       |
|----------------|----------------|
| `< 0.30`       | Auto-approve   |
| `0.30 – 0.69`  | Human review   |
| `≥ 0.70`       | Auto-deny      |

### Toxicity Categories

| Category   | Keywords (examples)                   | Weight |
|------------|---------------------------------------|--------|
| Hate       | hate, racist, bigot, slur             | +0.35  |
| Violence   | kill, murder, attack, bomb            | +0.40  |
| Spam       | buy now, click here, free money       | +0.20  |
| Profanity  | damn, hell, crap, stupid              | +0.10  |
| Explicit   | porn, nude, sex, xxx                  | +0.45  |
| Threat     | i will hurt, you will pay, watch out  | +0.50  |
| Self-harm  | suicide, self-harm, end my life       | +0.45  |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Groq API key** — free at [console.groq.com](https://console.groq.com)

### Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure .env (edit with your Groq API key)
#    GROQ_API_KEY=gsk_your_key_here

# 3. Start the server
python app.py

# 4. Open browser
#    http://localhost:5001
```

> **Note:** Default port is **5001** (configurable via `FLASK_PORT` in `.env`). This avoids conflict with other apps on port 5000.

---

## 🔐 Environment Variables

| Variable      | Required | Default | Description |
|---------------|----------|---------|-------------|
| `GROQ_API_KEY` | No*     | —       | Groq API key for LLM analysis |
| `FLASK_PORT`   | No      | `5001`  | Server port |
| `FLASK_DEBUG`  | No      | `false` | Enable Flask debug mode |

> *Without `GROQ_API_KEY`, the app still works using rule-based scoring only. LLM analysis shows a fallback message.

---

## 📊 API Endpoints

| Method | Endpoint              | Description                          |
|--------|-----------------------|--------------------------------------|
| `POST` | `/api/moderate`       | Submit content for moderation        |
| `GET`  | `/api/queue`          | List pending human-review items      |
| `POST` | `/api/review/<id>`    | Submit human approve/deny decision   |
| `GET`  | `/api/completed`      | List all finalized decisions         |
| `GET`  | `/api/stats`          | Dashboard aggregate stats            |

### `POST /api/moderate`

```json
{
  "text": "Content to moderate",
  "id": "optional-content-id",
  "metadata": {
    "source": "user-123",
    "category": "comment"
  }
}
```

**Response (auto-resolved):**
```json
{
  "status": "completed",
  "content_id": "uuid",
  "final_decision": "approve",
  "score": 0.0,
  "route": "auto_approve",
  "llm_analysis": "This content is safe…",
  "audit_log": [...]
}
```

**Response (flagged for review):**
```json
{
  "status": "pending_review",
  "review_id": "uuid",
  "score": 0.45,
  "reasons": ["hate:hate(+0.35)", "profanity:damn(+0.10)"],
  "llm_analysis": "This content contains…"
}
```

### `POST /api/review/<review_id>`

```json
{
  "decision": "approve",
  "comment": "False positive — context is literary criticism"
}
```

---

## 🔧 How HITL Pause/Resume Works

1. **PAUSE**: The LangGraph workflow is compiled with `interrupt_before=["human_review"]` and a `MemorySaver` checkpointer. When `auto_moderate` routes content to `human_review`, the graph execution stream is natively suspended and the thread state is frozen by the checkpointer.

2. **RESUME**: When a human submits a decision via `POST /api/review/<id>`, the backend locates the frozen thread via `thread_id`, injects the human decision using `graph.update_state()`, and resumes execution via `graph.stream(None, config)`. The workflow proceeds to `finalize` organically.

3. **AUDIT TRAIL**: Every node appends a timestamped event to `state.audit_log`. This gives a full chain-of-custody record viewable in the UI's audit modal.

---

## 🎨 Frontend Design

The UI is a single-file `index.html` with no build step:

- **Dark glassmorphism** theme with animated grid and floating gradient orbs
- **Syne + JetBrains Mono** typography
- **Stats dashboard** — 4 live counters (pending, auto-denied, auto-approved, human-reviewed)
- **Submit panel** — textarea + metadata fields + quick sample buttons
- **Review queue** — cards with score bars, reason tags, LLM analysis, approve/deny buttons
- **Completed list** — decision badges, route tags, human comments
- **Audit modal** — timestamped per-node execution history
- **Toast notifications** — slide-in feedback for all actions
- **Auto-refresh** — UI polls every 6 seconds for new items

---

## 📁 Project Structure

```
Task_3/
├── app.py              # LangGraph nodes + Flask API (single file)
├── index.html          # Dark-theme interactive frontend (single file)
├── requirements.txt    # Python dependencies
├── .env                # Environment config (GROQ_API_KEY, port, etc.)
├── README.md           # This file
├── test_client.py      # CLI test script for API endpoints
└── test_lg.py          # Minimal LangGraph smoke test
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| LLM analysis says "unavailable" | Set `GROQ_API_KEY` in `.env` |
| Port conflict | Change `FLASK_PORT` in `.env` (default: 5001) |
| Review button doesn't work | Item may already be resolved — check Completed tab |
| No items in queue | Submit borderline content (score 0.30–0.69) to trigger HITL |

---

## 🧪 Testing

### Quick Samples (via UI)

The UI includes 5 preset test buttons:
- **✓ Safe** — auto-approves (score ~0.0)
- **⚠ Borderline** — flags for human review (score ~0.45)
- **✕ Toxic** — auto-denies (score ≥ 0.70)
- **📧 Spam** — tests spam detection keywords
- **🔴 Threat** — tests threat detection keywords

### CLI Test

```bash
python test_client.py
```

This submits safe, toxic, and borderline content, then auto-approves the borderline item.

---

## 🔗 Resources

- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [LangGraph Human-in-the-Loop](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/)
- [Groq API Docs](https://console.groq.com/docs)
- [Flask Docs](https://flask.palletsprojects.com/)

---

**Built with ⚡ LangGraph HITL + Groq LLM + Flask**
