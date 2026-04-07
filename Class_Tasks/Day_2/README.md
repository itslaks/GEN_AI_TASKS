# 🎬 CineAI — Your AI-Powered Movie Recommendation Engine

> *"Don't scroll Netflix for 40 minutes again."*

CineAI recommends movies, TV series, and short films based on your **mood, genre taste, favourite actors, and franchises** — ranked using a **combined score** from IMDb audience ratings, Rotten Tomatoes critics, and Metacritic. Powered by **Groq LLaMA** for deep AI reasoning and **OMDb API** for real-world ratings data.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🧠 **AI Intent Extraction** | Groq LLaMA understands your mood, themes, and tone |
| ⭐ **IMDb Ratings + Votes** | Real audience scores — not just critics |
| 🍅 **Rotten Tomatoes** | Critics' percentage from official RT data |
| 🎯 **Metacritic Score** | Press/critic consensus score |
| 📊 **Combined Score** | Weighted formula: 50% IMDb + 30% RT + 20% Metacritic |
| 🖼️ **Movie Posters** | Full poster images via OMDb (with gorgeous gradient fallback) |
| 💬 **Best Review** | AI-selected highlight review for each title |
| 🎬 **Movies + Series + Shorts** | Toggle between content types |
| 🦸 **Hero/Actor Filter** | Search by your favourite actor |
| 🦇 **Franchise/Character** | Search by franchise (Batman, Marvel, etc.) |
| ⚡ **Fast Caching** | File-based cache avoids redundant API calls |
| 🔗 **IMDb Deep Links** | Direct links to every title's IMDb page |

---

## 🗂️ Project Structure

```
cineai/
│
├── main.py          # 🚀 Core app — FastAPI + LangChain engine + UI
├── config.py        # ⚙️  Settings loader from .env
├── .env             # 🔑 Your API keys (never commit this!)
├── requirements.txt # 📦 Python dependencies
├── cache/           # 💾 Auto-created — stores cached API responses
├── logs/            # 📋 Auto-created — app logs
└── data/            # 📁 Auto-created — reserved for future use
```

> **Only 2 Python files you need to edit:** `main.py` and `config.py`  
> Everything else is auto-generated at runtime. ✅

---

## 🔑 API Keys You Need

All APIs used are **free tier** — no credit card required!

### 1. 🤖 Groq API (Required — LLM Brain)
- Sign up free → [console.groq.com](https://console.groq.com)
- Get your API key → copy it
- Model used: `llama-3.1-8b-instant` (fast & free)

### 2. 🎥 OMDb API (Required — Ratings + Posters)
- Sign up free → [omdbapi.com/apikey.aspx](https://www.omdbapi.com/apikey.aspx)
- Free tier: **1,000 requests/day**
- Provides: IMDb ratings, Rotten Tomatoes %, Metacritic, poster images

---

## ⚙️ Setup & Installation

### Step 1 — Clone / Download the project
```bash
git clone https://github.com/yourname/cineai.git
cd cineai
```

### Step 2 — Create a virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Create your `.env` file
```bash
# Create .env in the project root
touch .env
```

Add your keys:
```env
# 🤖 Groq (Required)
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=llama-3.1-8b-instant

# 🎥 OMDb (Required)
OMDB_API_KEY=your_omdb_key_here

# ⚙️ App settings (optional — defaults work fine)
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
```

### Step 5 — Run the app! 🚀
```bash
python main.py
```

Then open your browser → **[http://localhost:8000](http://localhost:8000)**

---

## 📦 requirements.txt

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
httpx==0.27.2
langchain-core==0.3.0
langchain-groq==0.2.0
pydantic==2.9.0
pydantic-settings==2.5.2
python-dotenv==1.0.1
```

> Save this as `requirements.txt` in your project root.

---

## 🎯 How It Works

```
User Input (mood, genre, actor, franchise)
          │
          ▼
  🧠 Groq LLaMA extracts intent
  → genres, themes, moods, content types
  → suggests 8–12 specific movie/show titles
          │
          ▼
  🎥 OMDb API enriches each title
  → IMDb rating + vote count
  → Rotten Tomatoes %
  → Metacritic score
  → Poster image URL
  → Cast, Director, Runtime, Plot
          │
          ▼
  📊 Combined Score computed
  → 50% IMDb (audience) + 30% RT (critics) + 20% Metacritic
          │
          ▼
  🧠 Groq LLaMA re-ranks results
  → Picks best matches for your taste
  → Writes AI explanation for each pick
  → Generates "best review" highlight
  → Suggests similar titles
          │
          ▼
  🎨 Beautiful UI renders cards
  → Poster (or gradient fallback)
  → Ratings row with IMDb ⭐ RT 🍅 MC 🎯
  → AI reasoning + why it matches
  → Best review quote
  → IMDb deep link
```

---

## 🖥️ API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Main UI (browser) |
| `POST` | `/api/recommend` | Get recommendations |
| `GET` | `/health` | Health check |

### POST `/api/recommend` — Request Body

```json
{
  "preference": "A dark psychological thriller with twist endings",
  "watched": "Inception, Se7en",
  "count": 6,
  "genres": "Thriller, Drama",
  "hero_actor": "Brad Pitt",
  "character_ref": "Detective noir",
  "content_types": "movie,series"
}
```

---

## 🎨 UI Highlights

- 🌑 **Dark cinematic theme** with film-grain overlay
- 🖼️ **Real poster images** pulled from OMDb
- 🌈 **Gradient fallback posters** when no image is available (unique color per film)
- 📊 **Ratings row** — IMDb ⭐ · Rotten Tomatoes 🍅 · Metacritic 🎯
- 📈 **Combined score pill** on poster (colour-coded green/yellow/red)
- 💬 **Review highlight block** — best critic/audience quote per film
- ✅ **Why it matches** — 3 bullet-point reasons from the AI
- 💡 **"If you liked X…"** — cross-reference suggestion
- 🔗 **IMDb link** on every card

---

## 🔧 Configuration Options

Edit `config.py` or set via `.env`:

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Your Groq API key |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | LLM model to use |
| `OMDB_API_KEY` | — | Your OMDb API key |
| `PORT` | `8000` | Server port |
| `DEBUG` | `true` | Enable debug/reload |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `cache_ttl_seconds` | `3600` | Cache duration (1 hour) |

---

## ⚠️ Known Limitations

- **OMDb free tier** = 1,000 requests/day. Each recommendation request uses ~8–14 OMDb calls. With caching, this stretches well.
- **Short films** may have limited OMDb coverage — AI fallback kicks in automatically.
- **Very new releases** (last few weeks) may not appear in OMDb yet.

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---|---|
| `GROQ_API_KEY is not set` | Add your key to `.env` |
| No posters showing | Check your `OMDB_API_KEY` is valid |
| Slow first request | Normal — LLM + 8–14 OMDb calls in parallel. Cached after first run. |
| `JSONDecodeError` in logs | LLM returned malformed JSON — retry, it's a rare edge case |
| Port already in use | Change `PORT=8001` in `.env` |

---

## 🚀 Roadmap / Future Ideas

- [ ] 🌐 YouTube / JustWatch streaming availability links
- [ ] 💾 User watchlist (save recommendations)
- [ ] 🔍 Search by director or writer
- [ ] 📱 PWA mobile support
- [ ] 🌍 Regional language filtering
- [ ] 🧑‍🤝‍🧑 Social sharing of recommendation sets

---

## 🙏 Credits & Acknowledgements

- **[Groq](https://console.groq.com)** — Blazing fast LLaMA inference (free tier 💙)
- **[OMDb API](https://www.omdbapi.com)** — Movie data, ratings & posters
- **[LangChain](https://langchain.com)** — LLM orchestration framework
- **[FastAPI](https://fastapi.tiangolo.com)** — Modern Python web framework
- **[Bebas Neue + DM Sans](https://fonts.google.com)** — Typography

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<div align="center">

Made with ❤️ and 🎬 by a fellow cinephile

*Stop doomscrolling. Start watching.*

</div>