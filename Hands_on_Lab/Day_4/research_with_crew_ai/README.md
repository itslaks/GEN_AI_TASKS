# 🤖 CREW/AI — Content Generation Terminal

> **3-Agent CrewAI pipeline that generates polished Digital Literacy blog posts.**  
> Built by **Lakshan** · Stack: CrewAI + OpenAI + Flask + Vanilla HTML/CSS/JS

---

## 🧠 What Is This?

CREW/AI spins up a sequential 3-agent team that collaborates to produce high-quality blog posts on **Digital Life / Internet Literacy** topics — things like phishing, privacy hygiene, platform scams, and online wellbeing.

```
[Researcher] ──▶ [Writer] ──▶ [Editor]
    Brief          Draft        Final Markdown
```

Each agent has a specific role, persona, and instruction set. The output is a ready-to-publish Markdown blog post with title, meta description, outline, and suggested sources.

---

## 📦 Files

| File | Description |
|------|-------------|
| `index.html` | Retro-futuristic dark theme frontend (single file, no build step) |
| `backend.py` | Flask API server — hosts the CrewAI pipeline |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |
| `README.md` | This file |

---

## 🚀 Run Locally

### 1. Clone / download the project

```bash
git clone https://github.com/your-username/crewai-content-terminal
cd crewai-content-terminal
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your API key

```bash
cp .env.example .env
# Edit .env and add your real OPENAI_API_KEY
```

### 5. Start the backend

```bash
python backend.py
# ✅ Server starts at http://localhost:5000
```

### 6. Open the frontend

Open `index.html` in your browser directly (file://) **or** serve it with any static server:

```bash
# Python quick server
python -m http.server 3000
# Open http://localhost:3000/index.html
```

> Set the **Backend API URL** field in the UI to `http://localhost:5000`.

### 7. Generate a post

1. Enter a topic (e.g. *"How to spot phishing emails in 2025"*)
2. (Optional) Set audience, tone, word count
3. Click **⚡ INITIALIZE CREW**
4. Watch the agent log in the terminal — the 3 agents run sequentially
5. Copy or download the finished Markdown blog post

---

## ☁️ Deploy on Vercel (Free Tier)

Vercel's free hobby tier supports Python serverless functions via its Python runtime.

### Steps

1. **Push to GitHub** — commit all 5 files to a public or private repo.

2. **Import to Vercel**
   - Go to [vercel.com](https://vercel.com) → New Project → Import your repo.

3. **Add environment variable**
   - In Vercel dashboard → Settings → Environment Variables
   - Add: `OPENAI_API_KEY` = your real key
   - (Optional) `MODEL_NAME`, `MAX_TOKENS`, etc.

4. **Create `vercel.json`** in the repo root:

```json
{
  "version": 2,
  "builds": [
    { "src": "backend.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "backend.py" }
  ]
}
```

5. **Serve `index.html` statically** — Vercel auto-serves any HTML file at the root.  
   Update the **Backend API URL** in `index.html` to your Vercel deployment URL  
   (e.g. `https://your-project.vercel.app`).

6. **Deploy** — push a commit; Vercel auto-deploys.

### Vercel Free Tier Notes

| Concern | Notes |
|---------|-------|
| **Function timeout** | Free tier = 10s max execution. CrewAI with GPT-4o-mini is usually 15–40s. Upgrade to Pro (60s) or use background jobs. |
| **No filesystem writes** | `backend.py` writes nothing — all data is returned in the HTTP response. ✅ |
| **Cold starts** | First request after idle may take ~2s. Normal. |
| **Cost** | Vercel hosting is free; OpenAI API calls are billed to your account. |

---

## 🎨 Design Notes

### Frontend (`index.html`)
- **Aesthetic**: Retro-futuristic CRT terminal — scanline overlay, animated grid, floating particles, Orbitron + VT323 + Share Tech Mono fonts
- **Pipeline visual**: The 3 agent chips animate (glow, pulse) as each agent activates
- **Terminal log**: Real-time step markers with colour-coded agent tags (RES/WRI/EDI)
- **Output tabs**: Toggle between rendered Markdown and raw Markdown
- **Zero dependencies**: No React, no bundler — pure HTML/CSS/JS

### Backend (`backend.py`)
- **Why 3 agents?**
  - *Researcher* — ensures factual grounding; prevents the Writer from hallucinating specifics
  - *Writer* — focuses purely on craft; works from a structured brief, not raw prompts
  - *Editor* — acts as a quality gate; enforces safety, clarity, and consistent voice
- **Sequential workflow** — each agent's output becomes the next agent's context; no branching or retries
- **Domain enforcement** — each agent's `backstory` and task `description` explicitly constrain content to Digital Life / Internet Literacy, ban harmful instructions, and require caution language on factual claims
- **Metadata block** — the Editor appends a `<!-- METADATA … -->` JSON block that the backend strips and parses, giving the frontend structured data (title, meta desc, outline, citations)
- **No filesystem** — stateless; all output returned in the JSON response
- **Vercel-ready** — `handler = app` alias satisfies Vercel's Python WSGI convention

---

## 🛡️ Safety Policy

- Agents are explicitly instructed **never** to provide instructions enabling hacking, fraud, or abuse
- Every factual claim is softened with hedging language ("may", "can", "often")
- Citations are labelled **"suggested sources — verify before publishing"** (never fabricated)
- Content that could enable harm is removed by the Editor with a safe alternative provided

---

## 📄 License

MIT — free to use, modify, and deploy. Attribution appreciated.

---

*Made with ⚡ by Lakshan*
