# CineAI v6 (Day 2 Python)

Smart AI movie discovery platform (FastAPI + Groq + Ollama fallback + OMDb + TMDB) with interactive UI.

## Core capabilities

- Multi-mode search:
  - `Recommend`
  - `Movie Search` (single deep-detail card)
  - `Actor Search`
  - `Character Search`
  - `Mood Timeline` (light → intense ordering)
  - `Compare 2 Movies` (side-by-side data view)
- Ratings per title:
  - IMDb
  - Rotten Tomatoes
  - Metacritic
- Posters with fallback handling.
- India watch-provider detection with clickable OTT links.
- Structured reviews:
  - Critics review block
  - Audience review block

## Smart interaction features

- Click actor/director name → auto-open their works.
- Click similar-title chips → fetch similar movie recommendations.
- Click poster → expand/collapse deep details (reviews + insights).
- Breadcrumb navigation trail (Movie → Actor → Similar).
- Floating shortcuts help button (`?`) with quick key map.
- Keyboard shortcuts:
  - `Alt+1` Recommend
  - `Alt+2` Movie
  - `Alt+3` Actor
  - `Alt+4` Character
  - `Alt+5` Timeline
  - `Alt+6` Compare
  - `Alt+F` focus search
  - `Alt+S` run search

## Similarity intent handling

Queries like:
- `similar movies like sita ramam`
- `movies like interstellar`

are now interpreted as similarity intent and return titles matched by:
- similar genre
- similar story arc
- similar emotional tone

instead of generic not-found behavior.

## OTT and watchlist features

- Smart watchlist APIs:
  - `GET /api/watchlist`
  - `POST /api/watchlist/add`
  - `POST /api/watchlist/remove`
  - `POST /api/watchlist/check`
- Persistent watchlist storage in `data/watchlist.json`.
- OTT change tracking for India:
  - alerts when platforms change
  - per-title "new OTT" badges for newly added platforms.

## Trending

- `GET /api/trending` uses TMDB weekly trending.
- Cache refresh is daily (`YYYY-MM-DD`) for regular updates.

## Security hardening

- Rate limiting on public endpoints (IP + user dimensions).
- Strict input validation (schema + strict types + extra field rejection).
- Maximum input length cap: 397 chars.
- Basic injection/XSS payload rejection.
- Output sanitization before UI rendering.
- Secrets loaded from environment only.

## Environment variables

Required (for full functionality):
- `GROQ_API_KEY`
- `OMDB_API_KEY`
- `TMDB_API_KEY`

Optional:
- `GROQ_MODEL` (default `llama-3.1-8b-instant`)
- `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- `OLLAMA_MODEL` (default `mistral:latest`)
- `SIMILARITY_MIN_THRESHOLD` (default `35.0`, higher = stricter "similar movies" matching)
- `RATE_LIMIT_IP_WINDOW_SECONDS`
- `RATE_LIMIT_IP_MAX_REQUESTS`
- `RATE_LIMIT_USER_WINDOW_SECONDS`
- `RATE_LIMIT_USER_MAX_REQUESTS`

## Run

```bash
python main.py
```

Open:
- `http://localhost:8000`

## Notes

- Groq is primary (token-efficient settings).
- Local Ollama/Mistral is fallback.
- TMDB improves OTT/provider/review/trending richness.
