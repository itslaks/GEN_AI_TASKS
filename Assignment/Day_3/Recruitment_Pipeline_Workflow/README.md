# ⚡ Recruiter.AI — Neural Hiring Pipeline

A production-ready AI recruitment pipeline built with **LangGraph**, **Groq (LLaMA 3.1 8B Instant)**, and a sleek cyberpunk-dark Flask web app.

---

## 📁 File Structure

```
recruiter-ai/
├── app.py             ← Flask API + LangGraph pipeline (single file)
├── index.html         ← Frontend UI (dark theme, chatbot, pipeline viz)
├── requirements.txt   ← Python dependencies
├── recruitments.txt   ← Sample candidates + job data (JSON)
├── .env.example       ← Environment variable template
└── README.md          ← You are here
```

---

## 🚀 Quick Start

### 1. Install Dependencies (Python 3.10)

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
# Get a free key at: https://console.groq.com
```

### 3. Run the App

```bash
python app.py
```

Visit: **http://localhost:5000**

---

## 🧠 LangGraph Pipeline Architecture

```
START
  │
  ▼
[Agent 1: Resume Screening]
  │  LLM: parse, score, rank each resume
  ▼
[Router 1: screening_router]
  ├── needs_clarification → [Clarification Node] → ...
  └── shortlisted → [Agent 2: Interview Scheduling]
                           │  LLM: propose slots
                           │  Tool: calendar_api_check_availability
                           │  Tool: calendar_api_book_slot
                           │  Retry ≤ 2x on conflict
                           ▼
                    [Agent 3: Candidate Evaluation]
                           │  LLM: rubric scoring → hire/hold/reject
                           ▼
                    [Router 2: evaluation_router]
                           ├── confidence < 60% → [Human Review]
                           └── confident → END
```

---

## 🤖 LLM Configuration

| Setting        | Value                          |
|----------------|-------------------------------|
| Primary LLM    | Groq — `llama-3.1-8b-instant` |
| Fallback LLM   | Local Ollama — `mistral`       |
| Temperature    | 0.2 (deterministic)            |
| Max Tokens     | 2048                           |

To use local Mistral fallback:
```bash
ollama pull mistral
# Leave GROQ_API_KEY blank in .env
```

---

## 💬 ResumeChat Feature

The chatbot page allows you to interactively interrogate any candidate's resume:
- **"What are their top skills?"**
- **"Is this candidate a fit for Senior ML Engineer?"**
- **"What salary range would you estimate?"**
- **"Summarize their experience."**

The bot uses the candidate's raw resume text as context for each response.

---

## 🔧 Extending the System

### ATS Integration
Replace stub `calendar_api_*` functions in `app.py` with Greenhouse or Lever API calls. Map `candidate_id` to ATS record IDs.

### Email Notifications
Add SendGrid/SES calls in `request_clarification_node()` and post-evaluation to trigger real emails.

### Scoring Calibration
Store rubric weights per `job_id` in a database. Add a feedback loop node to adjust thresholds based on hire outcomes over time.

### Persistent State
Replace in-memory `resume_contexts` dict with Redis or PostgreSQL for multi-session persistence.

### Production Deployment
```bash
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

---

## 📊 State Schema (TypedDict)

| Field                  | Type                    | Description                         |
|------------------------|-------------------------|-------------------------------------|
| `job_id`               | `str`                   | Unique job identifier                |
| `job_description`      | `str`                   | Full JD text                         |
| `resumes`              | `List[dict]`            | Raw resume inputs                    |
| `screened_candidates`  | `List[ScreenedCandidate]` | Scored + ranked candidates          |
| `scheduling_requests`  | `List[SchedulingRequest]` | LLM-proposed time slots             |
| `interview_slots`      | `List[InterviewSlot]`   | Confirmed booked interviews          |
| `interview_notes`      | `List[InterviewNote]`   | Post-interview notes input           |
| `evaluations`          | `List[Evaluation]`      | Final hire/hold/reject decisions     |
| `audit_log`            | `List[AuditEntry]`      | Full event trail with timestamps     |
| `clarification_needed` | `List[str]`             | Candidate IDs needing more info      |
| `scheduling_retries`   | `dict`                  | Retry counter per candidate          |

---

## 🛡️ Tool Boundaries

| Layer           | What It Does                                      |
|-----------------|---------------------------------------------------|
| **LLM (Groq)**  | Resume parsing, slot proposal, rubric evaluation  |
| **Deterministic** | Score extraction, JSON parsing, deduplication   |
| **Stub Tools**  | `calendar_api_check_availability`, `calendar_api_book_slot` |
| **Idempotency** | `dedupe_by_candidate_id` — MD5 hash fallback      |

---

## ✅ Requirements

- Python 3.10
- Groq API key (free at https://console.groq.com) OR local Ollama with Mistral
- No other paid services required
