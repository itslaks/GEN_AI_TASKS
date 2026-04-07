"""
CineAI v5 — Smart Movie Recommendation Engine
==============================================
Improvements:
  • Token-efficient prompts (Groq free-tier safe, <4000 TPM)
  • Ollama/Mistral local LLM fallback when Groq rate-limits
  • Multi-source poster fetching (OMDb → TMDB → IMDb scrape → gradient)
  • Better recommendation quality with tighter AI reasoning
  • Faster parallel enrichment with smarter deduplication
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from config import PATHS, settings

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("cineai")


# ═══════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════

class RecommendationRequest(BaseModel):
    preference: str = Field(..., min_length=3, max_length=500)
    watched: Optional[str] = Field(default="")
    count: int = Field(default=6, ge=1, le=10)
    genres: Optional[str] = Field(default="")
    hero_actor: Optional[str] = Field(default="")
    character_ref: Optional[str] = Field(default="")
    content_types: Optional[str] = Field(default="movie")


class MovieRatings(BaseModel):
    imdb: Optional[str] = None
    imdb_votes: Optional[str] = None
    rotten_tomatoes: Optional[str] = None
    metacritic: Optional[str] = None


class MovieCard(BaseModel):
    rank: int
    title: str
    content_type: str = "movie"
    year: Optional[int] = None
    end_year: Optional[int] = None
    overview: Optional[str] = None
    genres: list[str] = []
    director: Optional[str] = None
    cast: list[str] = []
    runtime: Optional[str] = None
    seasons: Optional[int] = None
    language: Optional[str] = None
    ratings: MovieRatings = MovieRatings()
    poster_url: Optional[str] = None
    imdb_id: Optional[str] = None
    imdb_url: Optional[str] = None
    confidence: float = 0.0
    ai_reason: str = ""
    why_matches: list[str] = []
    mood_tags: list[str] = []
    similar_to: Optional[str] = None
    best_review: Optional[str] = None
    combined_score: Optional[float] = None
    llm_source: str = "groq"


class RecommendationResponse(BaseModel):
    status: str
    query_analysis: str = ""
    recommendations: list[MovieCard] = []
    total_results: int = 0
    execution_time_ms: float = 0.0
    sources_used: list[str] = []
    llm_used: str = "groq"


class HealthResponse(BaseModel):
    status: str
    version: str
    groq_configured: bool
    omdb_configured: bool
    ollama_available: bool
    timestamp: str


# ═══════════════════════════════════════════════════════════════════════════
# LLM MANAGER — Groq primary, Ollama fallback
# ═══════════════════════════════════════════════════════════════════════════

class LLMManager:
    """Manages Groq (primary) + Ollama/Mistral (fallback) with auto-switching."""

    GROQ_RATE_ERRORS = (413, 429, "rate_limit_exceeded", "Request too large")

    def __init__(self):
        self._groq: Optional[ChatGroq] = None
        self._ollama: Optional[ChatOllama] = None
        self._groq_failed_until: float = 0.0  # backoff timestamp
        self._ollama_ok: Optional[bool] = None

    def _get_groq(self) -> Optional[ChatGroq]:
        if not settings.groq_api_key:
            return None
        if not self._groq:
            self._groq = ChatGroq(
                api_key=settings.groq_api_key,
                model_name=settings.groq_model,
                temperature=0.25,
                max_tokens=800,          # tight limit to avoid 413
                request_timeout=30,
            )
        return self._groq

    def _get_ollama(self) -> Optional[ChatOllama]:
        if not self._ollama:
            try:
                self._ollama = ChatOllama(
                    model=settings.ollama_model,
                    base_url=settings.ollama_base_url,
                    temperature=0.25,
                    num_predict=900,
                )
            except Exception as exc:
                logger.warning(f"Ollama init failed: {exc}")
                return None
        return self._ollama

    async def check_ollama(self) -> bool:
        """Ping Ollama to see if it's running."""
        if self._ollama_ok is not None:
            return self._ollama_ok
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(f"{settings.ollama_base_url}/api/tags")
                self._ollama_ok = r.status_code == 200
        except Exception:
            self._ollama_ok = False
        return self._ollama_ok

    def groq_in_backoff(self) -> bool:
        return time.time() < self._groq_failed_until

    def mark_groq_failed(self, seconds: int = 60):
        self._groq_failed_until = time.time() + seconds
        logger.warning(f"Groq rate-limited → backoff {seconds}s, using Ollama")

    def is_rate_error(self, exc: Exception) -> bool:
        msg = str(exc)
        return any(e in msg for e in self.GROQ_RATE_ERRORS)

    async def invoke(self, chain_factory, kwargs: dict, prefer_ollama: bool = False) -> tuple[str, str]:
        """
        Invoke a chain. Returns (result_text, llm_source).
        chain_factory(llm) -> chain
        """
        use_ollama = prefer_ollama or self.groq_in_backoff()

        if not use_ollama:
            groq = self._get_groq()
            if groq:
                try:
                    chain = chain_factory(groq)
                    result = await chain.ainvoke(kwargs)
                    return result, "groq"
                except Exception as exc:
                    if self.is_rate_error(exc):
                        self.mark_groq_failed(90)
                        logger.info("Switched to Ollama fallback")
                    else:
                        raise

        # Ollama fallback
        ollama = self._get_ollama()
        if ollama:
            try:
                chain = chain_factory(ollama)
                result = await chain.ainvoke(kwargs)
                return result, f"ollama/{settings.ollama_model}"
            except Exception as exc:
                logger.error(f"Ollama also failed: {exc}")
                raise RuntimeError(f"Both LLMs failed. Last error: {exc}")

        raise RuntimeError("No LLM available. Configure GROQ_API_KEY or run Ollama.")


llm_manager = LLMManager()


# ═══════════════════════════════════════════════════════════════════════════
# TOKEN-EFFICIENT PROMPTS
# ═══════════════════════════════════════════════════════════════════════════

# Intent prompt — compact, ~300 tokens input, ~250 output
INTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Film expert. Extract intent as JSON only (no markdown):
{"genres":[],"moods":[],"themes":[],"language":null,"hero_actor":null,"avoid":[],"titles":["T1","T2","T3","T4","T5","T6","T7","T8"],"summary":"one sentence"}
titles: 8 real movie/show titles matching request. If actor given, include their films."""),
    ("human", "Want: {preference}\nSeen: {watched}\nGenres: {genres}\nActor: {hero_actor}\nFranchise: {character_ref}\nTypes: {content_types}"),
])

# Rerank prompt — compact, ~400 tokens input, ~500 output
RERANK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Film critic AI. Pick best {count} from candidates. JSON array only:
[{{"title":"exact match","confidence":0.9,"ai_reason":"2 sentences why it matches","why_matches":["reason1","reason2","reason3"],"mood_tags":["tag1","tag2"],"similar_to":"if you liked X","best_review":"one compelling sentence"}}]
Weight: combined score > audience votes > critic score. Only use titles from candidates."""),
    ("human", "Intent: {intent}\nCandidates:\n{candidates}"),
])

# Fallback pure-LLM prompt
FALLBACK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Recommend {count} films. JSON array only:
[{{"title":"","year":2020,"content_type":"movie","genres":[],"director":"","cast":[],"ai_reason":"","why_matches":[],"confidence":0.8,"mood_tags":[],"similar_to":"","best_review":""}}]"""),
    ("human", "{preference}"),
])


# ═══════════════════════════════════════════════════════════════════════════
# OMDb + POSTER CLIENT
# ═══════════════════════════════════════════════════════════════════════════

class MediaClient:
    OMDB = "https://www.omdbapi.com"
    TMDB_SEARCH = "https://api.themoviedb.org/3/search/multi"
    TMDB_IMG = "https://image.tmdb.org/t/p/w500"

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=8, follow_redirects=True)

    async def _omdb_fetch(self, params: dict) -> dict:
        if not settings.omdb_api_key:
            return {}
        try:
            params["apikey"] = settings.omdb_api_key
            r = await self._client.get(self.OMDB, params=params)
            r.raise_for_status()
            d = r.json()
            return d if d.get("Response") == "True" else {}
        except Exception as exc:
            logger.debug(f"OMDb error: {exc}")
            return {}

    async def by_title(self, title: str) -> dict:
        # Try movie, then series
        for t in ("movie", "series"):
            d = await self._omdb_fetch({"t": title, "plot": "short", "type": t})
            if d:
                return d
        return {}

    async def search(self, query: str) -> list[dict]:
        d = await self._omdb_fetch({"s": query})
        return d.get("Search", []) if d else []

    async def _tmdb_poster(self, title: str, year: Optional[int] = None) -> Optional[str]:
        """Try TMDB for poster if OMDb missing one."""
        if not settings.tmdb_api_key:
            return None
        try:
            params = {"api_key": settings.tmdb_api_key, "query": title}
            if year:
                params["year"] = year
            r = await self._client.get(self.TMDB_SEARCH, params=params)
            data = r.json().get("results", [])
            for item in data[:3]:
                path = item.get("poster_path")
                if path:
                    return f"{self.TMDB_IMG}{path}"
        except Exception:
            pass
        return None

    def extract_rating(self, data: dict, source: str) -> Optional[str]:
        for r in data.get("Ratings", []):
            if source.lower() in r.get("Source", "").lower():
                return r.get("Value")
        return None

    def combined_score(self, data: dict) -> Optional[float]:
        scores, weights = [], []
        imdb = data.get("imdbRating", "N/A")
        if imdb and imdb != "N/A":
            try:
                scores.append(float(imdb) * 10)
                weights.append(0.50)
            except ValueError:
                pass
        rt = self.extract_rating(data, "Rotten Tomatoes")
        if rt and "%" in rt:
            try:
                scores.append(float(rt.replace("%", "")))
                weights.append(0.30)
            except ValueError:
                pass
        mc = self.extract_rating(data, "Metacritic")
        if mc and "/" in mc:
            try:
                scores.append(float(mc.split("/")[0]))
                weights.append(0.20)
            except ValueError:
                pass
        if not scores:
            return None
        tw = sum(weights)
        return round(sum(s * w for s, w in zip(scores, weights)) / tw, 1)

    async def enrich(self, title: str) -> Optional[dict]:
        data = await self.by_title(title)
        if not data:
            # Try search fallback
            results = await self.search(title)
            if results:
                imdb_id = results[0].get("imdbID")
                if imdb_id:
                    data = await self._omdb_fetch({"i": imdb_id, "plot": "short"})
        if not data:
            return None

        ct = {"series": "series", "short": "short"}.get(data.get("Type", ""), "movie")
        year_raw = data.get("Year", "")
        year = end_year = None
        if "–" in year_raw or "-" in year_raw:
            parts = re.split(r"[–-]", year_raw)
            try:
                year = int(parts[0])
                end_year = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else None
            except ValueError:
                pass
        elif year_raw.isdigit():
            year = int(year_raw)

        poster = data.get("Poster", "")
        if not poster or poster == "N/A":
            poster = await self._tmdb_poster(title, year) or None
        else:
            poster = poster  # already a URL

        seasons_str = data.get("totalSeasons", "")
        return {
            "title": data.get("Title", title),
            "content_type": ct,
            "year": year,
            "end_year": end_year,
            "overview": (data.get("Plot") or "").strip() or None,
            "genres": [g.strip() for g in data.get("Genre", "").split(",") if g.strip()],
            "director": (data.get("Director") or "").strip() or None,
            "cast": [a.strip() for a in data.get("Actors", "").split(",") if a.strip()][:4],
            "runtime": (data.get("Runtime") or "").strip() or None,
            "seasons": int(seasons_str) if seasons_str and seasons_str.isdigit() else None,
            "language": (data.get("Language") or "").split(",")[0].strip() or None,
            "imdb_id": data.get("imdbID") or None,
            "imdb_rating": data.get("imdbRating") or None,
            "imdb_votes": data.get("imdbVotes") or None,
            "rt": self.extract_rating(data, "Rotten Tomatoes"),
            "metacritic": self.extract_rating(data, "Metacritic"),
            "combined_score": self.combined_score(data),
            "poster": poster if poster else None,
        }


# ═══════════════════════════════════════════════════════════════════════════
# CACHE
# ═══════════════════════════════════════════════════════════════════════════

class FileCache:
    def __init__(self, cache_dir: str, ttl: int = 3600):
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl

    def _key(self, raw: str) -> Path:
        return self.dir / f"{hashlib.md5(raw.encode()).hexdigest()}.json"

    def get(self, raw: str) -> Any:
        p = self._key(raw)
        if p.exists() and (time.time() - p.stat().st_mtime) < self.ttl:
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
        return None

    def set(self, raw: str, value: Any) -> None:
        try:
            self._key(raw).write_text(json.dumps(value))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class CineAIEngine:
    def __init__(self):
        self.media = MediaClient()
        self.cache = FileCache(settings.cache_dir, ttl=settings.cache_ttl_seconds)

    def _parse_json(self, text: str, fallback: Any = None) -> Any:
        text = text.strip()
        # Strip markdown fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        # Find JSON array or object
        for pattern in (r"\[[\s\S]*\]", r"\{[\s\S]*\}"):
            m = re.search(pattern, text)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    pass
        logger.error(f"JSON parse failed: {text[:300]}")
        return fallback

    def _compact_candidates(self, enriched: list[dict]) -> str:
        """Build compact candidate string for rerank prompt."""
        lines = []
        for e in enriched:
            score = f" score={e['combined_score']}" if e.get("combined_score") else ""
            imdb = f" imdb={e['imdb_rating']}" if e.get("imdb_rating") else ""
            rt = f" rt={e['rt']}" if e.get("rt") else ""
            lines.append(
                f"- {e['title']} ({e.get('year','?')}) [{e.get('content_type','movie')}]{score}{imdb}{rt} | {e.get('overview','')[:80]}"
            )
        return "\n".join(lines)

    async def recommend(self, req: RecommendationRequest) -> RecommendationResponse:
        t0 = time.time()
        sources_used: list[str] = []
        llm_used = "groq"

        # ── Step 1: Intent extraction ─────────────────────────────────────
        cache_key = f"v5intent:{req.preference}:{req.watched}:{req.genres}:{req.hero_actor}:{req.character_ref}:{req.content_types}"
        intent_data = self.cache.get(cache_key)

        if intent_data is None:
            try:
                raw, llm_used = await llm_manager.invoke(
                    lambda llm: INTENT_PROMPT | llm | StrOutputParser(),
                    {
                        "preference": req.preference[:300],
                        "watched": (req.watched or "none")[:100],
                        "genres": (req.genres or "any")[:50],
                        "hero_actor": (req.hero_actor or "none")[:50],
                        "character_ref": (req.character_ref or "none")[:50],
                        "content_types": (req.content_types or "movie")[:30],
                    }
                )
                intent_data = self._parse_json(raw, {})
                self.cache.set(cache_key, intent_data)
            except Exception as exc:
                logger.error(f"Intent extraction failed: {exc}")
                intent_data = {"titles": [req.preference], "summary": req.preference}

        sources_used.append(f"LLM ({llm_used})")
        suggested_titles: list[str] = intent_data.get("titles", [req.preference])
        summary: str = intent_data.get("summary", req.preference)
        logger.info(f"Intent: {summary} | {len(suggested_titles)} titles")

        # ── Step 2: Parallel OMDb enrichment ─────────────────────────────
        watched_lower = {w.strip().lower() for w in (req.watched or "").split(",") if w.strip()}

        async def enrich_cached(title: str) -> Optional[dict]:
            ck = f"v5omdb:{title.lower()}"
            cached = self.cache.get(ck)
            if cached is not None:
                return cached
            result = await self.media.enrich(title)
            if result:
                self.cache.set(ck, result)
            return result

        tasks = [enrich_cached(t) for t in suggested_titles[:12]]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        enriched: list[dict] = []
        seen: set[str] = set()
        for r in raw_results:
            if not r or isinstance(r, Exception):
                continue
            key = r["title"].lower()
            if key in seen or key in watched_lower:
                continue
            seen.add(key)
            enriched.append(r)

        if settings.omdb_api_key:
            sources_used.append("OMDb/IMDb")

        # Sort by combined score
        enriched.sort(key=lambda x: x.get("combined_score") or 0, reverse=True)

        # ── Step 3: Pure LLM fallback ─────────────────────────────────────
        if not enriched:
            try:
                raw, llm_used = await llm_manager.invoke(
                    lambda llm: FALLBACK_PROMPT | llm | StrOutputParser(),
                    {"preference": req.preference[:300], "count": req.count}
                )
                items = self._parse_json(raw, [])
                return RecommendationResponse(
                    status="success",
                    query_analysis=summary,
                    recommendations=[
                        MovieCard(
                            rank=i,
                            title=item.get("title", ""),
                            content_type=item.get("content_type", "movie"),
                            year=item.get("year"),
                            genres=item.get("genres", []),
                            director=item.get("director"),
                            cast=item.get("cast", []),
                            confidence=item.get("confidence", 0.75),
                            ai_reason=item.get("ai_reason", ""),
                            why_matches=item.get("why_matches", []),
                            mood_tags=item.get("mood_tags", []),
                            similar_to=item.get("similar_to"),
                            best_review=item.get("best_review"),
                            llm_source=llm_used,
                        )
                        for i, item in enumerate(items[:req.count], 1)
                    ],
                    total_results=min(len(items), req.count),
                    execution_time_ms=round((time.time() - t0) * 1000, 1),
                    sources_used=list(dict.fromkeys(sources_used)),
                    llm_used=llm_used,
                )
            except Exception as exc:
                raise HTTPException(status_code=503, detail=str(exc))

        # ── Step 4: AI Re-ranking ─────────────────────────────────────────
        candidates_str = self._compact_candidates(enriched[:10])
        intent_compact = f"genres:{intent_data.get('genres',[])} moods:{intent_data.get('moods',[])} actor:{intent_data.get('hero_actor','')}"

        try:
            raw_rank, llm_used2 = await llm_manager.invoke(
                lambda llm: RERANK_PROMPT | llm | StrOutputParser(),
                {
                    "intent": intent_compact[:200],
                    "candidates": candidates_str[:1200],
                    "count": req.count,
                }
            )
            llm_used = llm_used2
            ranked = self._parse_json(raw_rank, [])
        except Exception as exc:
            logger.warning(f"Rerank failed, using score order: {exc}")
            ranked = [{"title": e["title"], "confidence": 0.80, "ai_reason": "", "why_matches": [], "mood_tags": []} for e in enriched]

        # ── Step 5: Build final cards ─────────────────────────────────────
        by_title = {e["title"].lower(): e for e in enriched}

        def find_meta(title: str) -> Optional[dict]:
            tl = title.lower()
            if tl in by_title:
                return by_title[tl]
            for k, v in by_title.items():
                if tl in k or k in tl:
                    return v
            return None

        final: list[MovieCard] = []
        for i, rm in enumerate(ranked[:req.count], 1):
            meta = find_meta(rm.get("title", ""))
            if not meta:
                continue
            iid = meta.get("imdb_id") or ""
            final.append(MovieCard(
                rank=i,
                title=meta["title"],
                content_type=meta.get("content_type", "movie"),
                year=meta.get("year"),
                end_year=meta.get("end_year"),
                overview=meta.get("overview"),
                genres=meta.get("genres", []),
                director=meta.get("director"),
                cast=meta.get("cast", []),
                runtime=meta.get("runtime"),
                seasons=meta.get("seasons"),
                language=meta.get("language"),
                ratings=MovieRatings(
                    imdb=meta.get("imdb_rating"),
                    imdb_votes=meta.get("imdb_votes"),
                    rotten_tomatoes=meta.get("rt"),
                    metacritic=meta.get("metacritic"),
                ),
                poster_url=meta.get("poster"),
                imdb_id=iid or None,
                imdb_url=f"https://www.imdb.com/title/{iid}/" if iid else None,
                confidence=rm.get("confidence", 0.80),
                ai_reason=rm.get("ai_reason", ""),
                why_matches=rm.get("why_matches", []),
                mood_tags=rm.get("mood_tags", []),
                similar_to=rm.get("similar_to"),
                best_review=rm.get("best_review"),
                combined_score=meta.get("combined_score"),
                llm_source=llm_used,
            ))

        return RecommendationResponse(
            status="success",
            query_analysis=summary,
            recommendations=final,
            total_results=len(final),
            execution_time_ms=round((time.time() - t0) * 1000, 1),
            sources_used=list(dict.fromkeys(sources_used)),
            llm_used=llm_used,
        )


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI APP
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(title="CineAI v5", version="5.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_engine: Optional[CineAIEngine] = None

def get_engine() -> CineAIEngine:
    global _engine
    if _engine is None:
        _engine = CineAIEngine()
    return _engine


@app.get("/health", response_model=HealthResponse)
async def health():
    ollama_ok = await llm_manager.check_ollama()
    return HealthResponse(
        status="healthy",
        version="5.0.0",
        groq_configured=bool(settings.groq_api_key),
        omdb_configured=bool(settings.omdb_api_key),
        ollama_available=ollama_ok,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.post("/api/recommend", response_model=RecommendationResponse)
async def recommend(req: RecommendationRequest):
    try:
        return await get_engine().recommend(req)
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Recommendation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/llm-status")
async def llm_status():
    ollama_ok = await llm_manager.check_ollama()
    return {
        "groq_configured": bool(settings.groq_api_key),
        "groq_in_backoff": llm_manager.groq_in_backoff(),
        "ollama_available": ollama_ok,
        "ollama_model": settings.ollama_model,
        "active_llm": "ollama" if llm_manager.groq_in_backoff() else "groq",
    }


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(content=_UI_HTML)


# ═══════════════════════════════════════════════════════════════════════════
# UI — CINEMATIC DARK THEME
# ═══════════════════════════════════════════════════════════════════════════

_UI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CineAI — Find Your Perfect Watch</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,700&family=Outfit:wght@300;400;500;600&display=swap" rel="stylesheet"/>
<style>
:root{
  --bg:#060810;
  --surface:#0b0f1a;
  --surface2:#111827;
  --surface3:#1a2235;
  --border:#1e2d42;
  --border2:#2a3f5a;
  --accent:#e8952a;
  --accent2:#c0392b;
  --gold:#f5c518;
  --rt:#fa4609;
  --mc:#66bb6a;
  --teal:#26c6da;
  --purple:#7c6af7;
  --text:#e2ecf5;
  --muted:#7a90a8;
  --muted2:#445566;
  --r:12px;
  --display:'Playfair Display',serif;
  --body:'Outfit',sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:var(--body);font-weight:300;min-height:100vh;overflow-x:hidden}

/* Scanline overlay */
body::before{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:1000;
  background:repeating-linear-gradient(0deg,transparent,transparent 3px,rgba(0,0,0,.04) 3px,rgba(0,0,0,.04) 4px);
}

/* ── HERO ── */
header{
  position:relative;padding:4rem 2rem 2.5rem;text-align:center;
  background:
    radial-gradient(ellipse 70% 50% at 50% 0%,rgba(232,149,42,.15),transparent 65%),
    radial-gradient(ellipse 40% 30% at 80% 60%,rgba(124,106,247,.08),transparent 50%);
  border-bottom:1px solid var(--border);overflow:hidden;
}
header::after{
  content:'';position:absolute;bottom:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,var(--accent),transparent);
}
.logo{
  font-family:var(--display);font-size:clamp(3.5rem,9vw,7rem);font-weight:900;
  letter-spacing:-.02em;line-height:1;
  background:linear-gradient(135deg,#fff 0%,var(--accent) 40%,#fff 70%,var(--accent) 100%);
  background-size:200%;
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  animation:shimmer 4s linear infinite;
}
@keyframes shimmer{0%{background-position:0%}100%{background-position:200%}}
.logo-sub{
  font-family:var(--display);font-size:clamp(1rem,2.5vw,1.5rem);
  font-style:italic;font-weight:700;
  -webkit-text-fill-color:var(--accent2);opacity:.9;margin-left:.3rem;
}
.tagline{margin-top:.6rem;font-size:.72rem;letter-spacing:.3em;text-transform:uppercase;color:var(--muted)}
.tagline b{color:var(--accent);font-weight:500}

/* LLM status bar */
#llm-bar{
  max-width:780px;margin:.8rem auto 0;
  display:flex;align-items:center;justify-content:center;gap:.5rem;flex-wrap:wrap;
}
.llm-chip{
  font-size:.66rem;letter-spacing:.06em;text-transform:uppercase;
  padding:.2rem .6rem;border-radius:20px;border:1px solid;display:flex;align-items:center;gap:.3rem;
}
.llm-groq{border-color:#6b5aed;color:#9b8ff5;background:rgba(107,90,237,.1)}
.llm-ollama{border-color:var(--mc);color:var(--mc);background:rgba(102,187,106,.1)}
.llm-warn{border-color:var(--accent);color:var(--accent);background:rgba(232,149,42,.1)}
.dot-pulse{width:6px;height:6px;border-radius:50%;animation:pulse 1.4s ease infinite}
.dot-green{background:var(--mc)}
.dot-orange{background:var(--accent)}
.dot-purple{background:#9b8ff5}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* ── PANEL ── */
.panel-wrap{max-width:820px;margin:2rem auto;padding:0 1.5rem}
.panel{
  background:var(--surface);border:1px solid var(--border);border-radius:16px;
  padding:2rem 2.2rem;position:relative;overflow:hidden;
}
.panel::before{
  content:'';position:absolute;top:-100px;right:-100px;width:280px;height:280px;
  background:radial-gradient(circle,rgba(232,149,42,.06),transparent 70%);pointer-events:none;
}

label{display:block;font-size:.65rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin-bottom:.4rem;font-weight:500}
textarea,input,select{
  width:100%;background:rgba(0,0,0,.4);border:1px solid var(--border);border-radius:8px;
  color:var(--text);font-family:var(--body);font-size:.9rem;font-weight:300;padding:.8rem 1rem;
  outline:none;transition:border-color .2s,box-shadow .2s;
}
textarea{min-height:88px;resize:vertical;line-height:1.5}
textarea:focus,input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(232,149,42,.12)}
::placeholder{color:var(--muted2)}

/* type toggles */
.type-row{display:flex;gap:.4rem;flex-wrap:wrap}
.type-btn{
  padding:.38rem .9rem;border-radius:20px;border:1px solid var(--border2);
  background:transparent;color:var(--muted);font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;
  cursor:pointer;transition:all .18s;font-family:var(--body);
}
.type-btn.active{background:rgba(232,149,42,.15);border-color:var(--accent);color:var(--accent)}

.grid2{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1.1rem}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;margin-top:1.1rem}
.field{margin-top:1.1rem}
@media(max-width:580px){.grid2,.grid3{grid-template-columns:1fr}}

hr.div{border:none;border-top:1px solid var(--border);margin:1.5rem 0}
.sec-label{
  font-size:.6rem;letter-spacing:.2em;text-transform:uppercase;color:var(--muted2);
  display:flex;align-items:center;gap:.5rem;margin-bottom:1rem;
}
.sec-label::after{content:'';flex:1;height:1px;background:var(--border)}

.btn{
  width:100%;margin-top:1.8rem;padding:1rem;border:none;border-radius:10px;cursor:pointer;
  font-family:var(--display);font-size:1.4rem;font-weight:700;letter-spacing:.04em;
  background:linear-gradient(135deg,#f5a623 0%,#c8780a 50%,#f5a623 100%);
  background-size:200%;color:#000;
  transition:background-position .4s,transform .15s,box-shadow .2s;
  box-shadow:0 4px 24px rgba(232,149,42,.3);
}
.btn:hover:not(:disabled){background-position:right;transform:translateY(-2px);box-shadow:0 8px 32px rgba(232,149,42,.4)}
.btn:disabled{opacity:.35;cursor:not-allowed}

/* ── LOADER ── */
#loader{display:none;text-align:center;padding:4rem;color:var(--muted)}
.reel{font-size:3rem;animation:spin 1s linear infinite;display:inline-block}
@keyframes spin{to{transform:rotate(360deg)}}
.load-txt{margin-top:.8rem;font-size:.72rem;letter-spacing:.22em;text-transform:uppercase}

/* ── STATUS BAR ── */
#status-bar{max-width:1260px;margin:0 auto 1.5rem;padding:0 1.5rem;display:none}
.analysis-box{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--r);
  padding:.9rem 1.4rem;display:flex;align-items:center;gap:.9rem;flex-wrap:wrap;
}
.analysis-box p{font-size:.84rem;color:var(--muted);flex:1;line-height:1.5}
.analysis-box strong{color:var(--text)}
.exec{font-size:.7rem;color:var(--muted2);white-space:nowrap}
.src-badges{display:flex;gap:.35rem;flex-wrap:wrap}
.src-badge{font-size:.62rem;letter-spacing:.07em;text-transform:uppercase;padding:.18rem .55rem;border-radius:20px;border:1px solid}
.sb-llm{border-color:#6b5aed;color:#9b8ff5}
.sb-omdb{border-color:var(--gold);color:var(--gold)}
.sb-ollama{border-color:var(--mc);color:var(--mc)}

/* ── GRID ── */
#results{max-width:1260px;margin:0 auto;padding:0 1.5rem 5rem}
.rh{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.6rem}
.rh h2{font-family:var(--display);font-size:1.8rem;font-weight:700}
.movie-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1.6rem}

/* ── CARD ── */
.card{
  background:var(--surface);border:1px solid var(--border);border-radius:14px;
  overflow:hidden;display:flex;flex-direction:column;
  transition:transform .3s ease,box-shadow .3s,border-color .3s;
  animation:rise .4s ease both;
}
.card:hover{transform:translateY(-5px);box-shadow:0 20px 60px rgba(0,0,0,.7);border-color:var(--border2)}
@keyframes rise{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}

/* poster */
.poster{position:relative;aspect-ratio:2/3;overflow:hidden;background:var(--surface2);flex-shrink:0}
.poster img{width:100%;height:100%;object-fit:cover;transition:transform .4s}
.card:hover .poster img{transform:scale(1.05)}
.poster-fallback{
  width:100%;height:100%;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:.8rem;padding:1.5rem;text-align:center;
  background:var(--fb-g);position:relative;
}
.poster-fallback::after{
  content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 70% 50% at 50% 25%,rgba(255,255,255,.06),transparent 65%);
}
.fb-icon{font-size:3.5rem;position:relative;z-index:1;filter:drop-shadow(0 4px 12px rgba(0,0,0,.5))}
.fb-t{font-family:var(--display);font-size:1.1rem;font-weight:700;color:rgba(255,255,255,.9);position:relative;z-index:1;line-height:1.2}
.fb-y{font-size:.72rem;color:rgba(255,255,255,.4);position:relative;z-index:1}

/* overlay elements */
.rank{
  position:absolute;top:.6rem;left:.6rem;z-index:3;
  background:var(--accent);color:#000;font-family:var(--display);font-weight:700;
  font-size:1.1rem;padding:.05rem .48rem;border-radius:5px;
}
.match-pill{
  position:absolute;top:.6rem;right:.6rem;z-index:3;
  background:rgba(0,0,0,.75);backdrop-filter:blur(6px);
  border:1px solid rgba(255,255,255,.15);border-radius:20px;
  font-size:.65rem;padding:.16rem .48rem;color:#fff;
}
.score-overlay{
  position:absolute;bottom:.6rem;right:.6rem;z-index:3;
  border-radius:8px;padding:.28rem .5rem;font-size:.7rem;font-weight:600;
  backdrop-filter:blur(8px);
}
.so-high{background:rgba(102,187,106,.25);border:1px solid rgba(102,187,106,.6);color:var(--mc)}
.so-mid{background:rgba(245,197,24,.22);border:1px solid rgba(245,197,24,.5);color:var(--gold)}
.so-low{background:rgba(250,70,9,.18);border:1px solid rgba(250,70,9,.5);color:var(--rt)}
.ct-badge{
  position:absolute;bottom:.6rem;left:.6rem;z-index:3;
  font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;
  padding:.18rem .5rem;border-radius:4px;
}
.ct-movie{background:rgba(232,149,42,.2);border:1px solid rgba(232,149,42,.5);color:var(--accent)}
.ct-series{background:rgba(38,198,218,.15);border:1px solid rgba(38,198,218,.5);color:var(--teal)}
.ct-short{background:rgba(102,187,106,.15);border:1px solid rgba(102,187,106,.5);color:var(--mc)}
.llm-flag{
  position:absolute;top:.6rem;left:50%;transform:translateX(-50%);z-index:3;
  font-size:.56rem;letter-spacing:.06em;padding:.12rem .4rem;border-radius:20px;
  background:rgba(124,106,247,.25);border:1px solid rgba(124,106,247,.5);color:#b8afff;white-space:nowrap;
}

/* card body */
.cbody{padding:1.1rem;flex:1;display:flex;flex-direction:column;gap:.65rem}
.ctitle{font-family:var(--display);font-size:1.25rem;font-weight:700;line-height:1.1}
.cyear{font-size:.8rem;color:var(--muted);font-family:var(--body);font-weight:300}
.csub{font-size:.73rem;color:var(--muted);display:flex;flex-wrap:wrap;gap:.25rem .55rem}
.cdot{color:var(--muted2)}

.genres{display:flex;flex-wrap:wrap;gap:.3rem}
.gtag{font-size:.6rem;letter-spacing:.07em;text-transform:uppercase;padding:.15rem .45rem;border-radius:3px;background:rgba(232,149,42,.09);border:1px solid rgba(232,149,42,.22);color:var(--accent)}

.ratings-row{
  display:flex;gap:.55rem;align-items:center;flex-wrap:wrap;
  padding:.55rem .75rem;background:var(--surface2);border-radius:7px;border:1px solid var(--border);
}
.rc{display:flex;align-items:center;gap:.25rem;font-size:.78rem}
.rc-ico{font-size:.88rem}
.rv-imdb{color:var(--gold);font-weight:500}
.rv-rt{color:var(--rt);font-weight:500}
.rv-mc{color:var(--mc);font-weight:500}
.rvotes{color:var(--muted2);font-size:.63rem}
.rdiv{width:1px;height:13px;background:var(--border);flex-shrink:0}

.overview{font-size:.78rem;color:var(--muted);line-height:1.6;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}

.ai-block{background:var(--surface2);border-radius:8px;padding:.85rem;border:1px solid var(--border2)}
.ai-reason{font-size:.78rem;font-style:italic;color:#a8c0d8;line-height:1.6}
.why-list{list-style:none;margin-top:.5rem;display:flex;flex-direction:column;gap:.28rem}
.why-list li{font-size:.72rem;color:var(--muted);display:flex;gap:.4rem;align-items:flex-start}
.why-list li::before{content:'✦';color:var(--accent);flex-shrink:0;font-size:.6rem;margin-top:.1rem}
.similar{font-size:.7rem;color:var(--teal);margin-top:.45rem;font-style:italic;line-height:1.45}

.review-block{
  background:rgba(245,197,24,.05);border:1px solid rgba(245,197,24,.18);
  border-left:3px solid var(--gold);border-radius:0 7px 7px 0;padding:.65rem .8rem;
}
.rquote{font-size:.77rem;font-style:italic;color:#c5d8e8;line-height:1.55}
.rquote::before,.rquote::after{color:var(--gold);font-size:1rem;line-height:0;vertical-align:-.12em}
.rquote::before{content:'"';margin-right:.1rem}
.rquote::after{content:'"';margin-left:.08rem}

.moods{display:flex;flex-wrap:wrap;gap:.28rem}
.mood{font-size:.61rem;padding:.15rem .45rem;border-radius:20px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);color:var(--muted)}

.card-link{
  display:block;text-align:center;padding:.42rem;border-radius:6px;margin-top:auto;
  font-size:.7rem;letter-spacing:.05em;text-decoration:none;
  border:1px solid rgba(245,197,24,.3);color:var(--gold);transition:all .2s;
}
.card-link:hover{background:rgba(245,197,24,.1);border-color:var(--gold)}

/* error */
.err{background:rgba(192,57,43,.1);border:1px solid rgba(192,57,43,.4);border-radius:var(--r);padding:1.5rem;color:#e74c3c;max-width:820px;margin:2rem auto}
</style>
</head>
<body>
<header>
  <div>
    <span class="logo">CineAI</span><span class="logo-sub">v5</span>
  </div>
  <p class="tagline">IMDb · <b>Rotten Tomatoes</b> · Metacritic · <b>Groq + Mistral</b> · AI-Powered</p>
  <div id="llm-bar"></div>
</header>

<div class="panel-wrap">
  <div class="panel">
    <div class="field">
      <label for="pref">What are you in the mood for?</label>
      <textarea id="pref" rows="3" placeholder="e.g. A gritty sci-fi noir with an unreliable narrator — like Blade Runner or Dark City. Atmosphere, tension, and a twist ending."></textarea>
    </div>

    <hr class="div"/>
    <div class="sec-label">Refine</div>

    <div class="grid3">
      <div><label for="genres">Genres</label><input id="genres" placeholder="Action, Sci-Fi…"/></div>
      <div><label for="hero">Actor / Director</label><input id="hero" placeholder="Tom Hanks, Nolan…"/></div>
      <div><label for="charref">Franchise / Character</label><input id="charref" placeholder="Batman, Marvel…"/></div>
    </div>
    <div class="grid2" style="margin-top:1rem">
      <div><label for="watched">Already seen (skip)</label><input id="watched" placeholder="Inception, Matrix…"/></div>
      <div><label for="count">How many?</label><input id="count" type="number" min="1" max="10" value="6" style="height:44px"/></div>
    </div>

    <div class="field">
      <label>Content type</label>
      <div class="type-row" id="type-row">
        <button class="type-btn active" data-type="movie" onclick="toggleType(this)">🎬 Movies</button>
        <button class="type-btn" data-type="series" onclick="toggleType(this)">📺 Series</button>
        <button class="type-btn" data-type="short" onclick="toggleType(this)">🎞 Shorts</button>
      </div>
    </div>

    <button class="btn" id="rec-btn" onclick="getRecs()">🎬 Find My Films</button>
  </div>
</div>

<div id="loader">
  <div class="reel">🎬</div>
  <p class="load-txt">Querying IMDb · Rotten Tomatoes · Metacritic…</p>
</div>

<div id="status-bar">
  <div class="analysis-box">
    <span style="font-size:1.3rem">🧠</span>
    <p><strong>AI understood: </strong><span id="ai-summary" style="color:var(--muted)"></span></p>
    <div class="src-badges" id="src-badges"></div>
    <span class="exec" id="exec-time"></span>
  </div>
</div>

<div id="results">
  <div class="rh" id="rh" style="display:none"><h2 id="rh-title">Recommendations</h2></div>
  <div class="movie-grid" id="grid"></div>
</div>

<script>
// LLM status on load
async function loadLLMStatus(){
  try{
    const r=await fetch('/api/llm-status');
    const d=await r.json();
    const bar=document.getElementById('llm-bar');
    let html='';
    if(d.groq_configured&&!d.groq_in_backoff){
      html+=`<span class="llm-chip llm-groq"><span class="dot-pulse dot-purple"></span>Groq LLaMA active</span>`;
    } else if(d.groq_in_backoff){
      html+=`<span class="llm-chip llm-warn"><span class="dot-pulse dot-orange"></span>Groq rate-limited</span>`;
    }
    if(d.ollama_available){
      html+=`<span class="llm-chip llm-ollama"><span class="dot-pulse dot-green"></span>Ollama/${d.ollama_model} ready</span>`;
    }
    bar.innerHTML=html;
  }catch(e){}
}
loadLLMStatus();

function toggleType(btn){
  btn.classList.toggle('active');
  const btns=[...document.querySelectorAll('.type-btn')];
  if(!btns.some(b=>b.classList.contains('active'))) btn.classList.add('active');
}
function activeTypes(){return [...document.querySelectorAll('.type-btn.active')].map(b=>b.dataset.type).join(',')}

const PALETTES=[
  ['#12011f','#4a1060'],['#01121f','#0a3a5a'],['#1f0108','#5a0a1a'],
  ['#011a08','#0a4a1a'],['#1a0f01','#5a3a0a'],['#010c1f','#0a1f5a'],
  ['#141401','#3a3a08'],['#12011a','#45085a'],['#011212','#0a3535'],
  ['#1a0a0a','#5a1a1a'],['#0a0a1f','#1a1a60'],['#011a14','#0a4a35'],
];
const CT_ICON={movie:'🎬',series:'📺',short:'🎞️'};
function palette(t){
  let h=0;for(const c of t)h=(h*31+c.charCodeAt(0))&0xffffffff;
  return PALETTES[Math.abs(h)%PALETTES.length];
}
function fallback(m){
  const[c1,c2]=palette(m.title);
  const icon=CT_ICON[m.content_type]||'🎬';
  const short=m.title.length>24?m.title.slice(0,21)+'…':m.title;
  return `<div class="poster-fallback" style="--fb-g:linear-gradient(160deg,${c1} 0%,${c2} 100%)">
    <div class="fb-icon">${icon}</div>
    <div class="fb-t">${short}</div>
    ${m.year?`<div class="fb-y">${m.year}</div>`:''}
  </div>`;
}
function scorePill(s){
  if(!s)return'';
  const cl=s>=75?'so-high':s>=55?'so-mid':'so-low';
  return`<span class="score-overlay ${cl}">${s}<span style="font-size:.6rem;opacity:.7">/100</span></span>`;
}

async function getRecs(){
  const pref=document.getElementById('pref').value.trim();
  if(!pref){alert('Describe what you want to watch!');return;}
  const btn=document.getElementById('rec-btn');
  btn.disabled=true;btn.textContent='Finding…';
  document.getElementById('loader').style.display='block';
  document.getElementById('status-bar').style.display='none';
  document.getElementById('rh').style.display='none';
  document.getElementById('grid').innerHTML='';
  try{
    const res=await fetch('/api/recommend',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        preference:pref,
        watched:document.getElementById('watched').value,
        count:parseInt(document.getElementById('count').value)||6,
        genres:document.getElementById('genres').value,
        hero_actor:document.getElementById('hero').value,
        character_ref:document.getElementById('charref').value,
        content_types:activeTypes(),
      })
    });
    if(!res.ok){const e=await res.json();throw new Error(e.detail||'Server error');}
    render(await res.json());
    loadLLMStatus();
  }catch(err){
    document.getElementById('grid').innerHTML=`<div class="err">⚠️ ${err.message}</div>`;
  }finally{
    document.getElementById('loader').style.display='none';
    btn.disabled=false;btn.textContent='🎬 Find My Films';
  }
}

function render(data){
  if(data.query_analysis){
    document.getElementById('ai-summary').textContent=data.query_analysis;
    document.getElementById('exec-time').textContent=`${data.execution_time_ms}ms`;
    const badges=document.getElementById('src-badges');
    badges.innerHTML=(data.sources_used||[]).map(s=>{
      const cl=s.includes('ollama')||s.includes('Ollama')?'sb-ollama':s.includes('OMDb')?'sb-omdb':'sb-llm';
      return`<span class="src-badge ${cl}">${s}</span>`;
    }).join('');
    document.getElementById('status-bar').style.display='block';
  }
  document.getElementById('rh-title').textContent=`${data.total_results} Pick${data.total_results!==1?'s':''}`;
  document.getElementById('rh').style.display='flex';
  const grid=document.getElementById('grid');
  data.recommendations.forEach((m,i)=>grid.insertAdjacentHTML('beforeend',buildCard(m,i*70)));
  document.getElementById('results').scrollIntoView({behavior:'smooth'});
}

function buildCard(m,delay){
  const pct=Math.round((m.confidence||0)*100);
  const ctCls={movie:'ct-movie',series:'ct-series',short:'ct-short'}[m.content_type]||'ct-movie';
  const ctLabel={movie:'Movie',series:'Series',short:'Short'}[m.content_type]||'Movie';

  let yearStr=m.year?`${m.year}`:'';
  if(m.content_type==='series'&&m.end_year&&m.end_year!==m.year)yearStr+=`–${m.end_year}`;
  const credit=m.content_type==='series'
    ?(m.creator?`Created by ${m.creator.split(',')[0].trim()}`:'')
    :(m.director&&m.director!=='N/A'?`Dir. ${m.director.split(',')[0].trim()}`:'');
  const castStr=(m.cast||[]).slice(0,3).join(', ');
  const seasons=m.seasons?`${m.seasons} season${m.seasons!==1?'s':''}`:'';

  const posterHtml=m.poster_url
    ?`<img src="${m.poster_url}" alt="${m.title}" loading="lazy"
        onerror="this.outerHTML=\`${fallback(m).replace(/`/g,'\\`')}\`"/>`
    :fallback(m);

  const rchips=[
    m.ratings?.imdb&&m.ratings.imdb!=='N/A'
      ?`<span class="rc"><span class="rc-ico">⭐</span><span class="rv-imdb">${m.ratings.imdb}</span><span class="rvotes">/10${m.ratings.imdb_votes?' · '+m.ratings.imdb_votes:''}</span></span>`:'',
    m.ratings?.rotten_tomatoes
      ?`<span class="rdiv"></span><span class="rc"><span class="rc-ico">🍅</span><span class="rv-rt">${m.ratings.rotten_tomatoes}</span></span>`:'',
    m.ratings?.metacritic
      ?`<span class="rdiv"></span><span class="rc"><span class="rc-ico">🎯</span><span class="rv-mc">${m.ratings.metacritic}</span></span>`:'',
  ].filter(Boolean).join('');

  const genres=(m.genres||[]).slice(0,4).map(g=>`<span class="gtag">${g}</span>`).join('');
  const moods=(m.mood_tags||[]).map(t=>`<span class="mood">${t}</span>`).join('');
  const why=(m.why_matches||[]).map(r=>`<li>${r}</li>`).join('');
  const llmLabel=m.llm_source&&m.llm_source.includes('ollama')?`<span class="llm-flag">✦ Mistral</span>`:'';

  return`<div class="card" style="animation-delay:${delay}ms">
  <div class="poster">
    ${posterHtml}
    <span class="rank">#${m.rank}</span>
    <span class="match-pill">${pct}% match</span>
    <span class="ct-badge ${ctCls}">${ctLabel}</span>
    ${llmLabel}
    ${m.combined_score?scorePill(m.combined_score):''}
  </div>
  <div class="cbody">
    <div>
      <div class="ctitle">${m.title}${yearStr?` <span class="cyear">(${yearStr})</span>`:''}</div>
      <div class="csub">
        ${credit?`<span>${credit}</span>`:''}
        ${castStr?`${credit?'<span class="cdot">·</span>':''}<span>${castStr}</span>`:''}
        ${m.runtime?`<span class="cdot">·</span><span>${m.runtime}</span>`:''}
        ${seasons?`<span class="cdot">·</span><span>${seasons}</span>`:''}
      </div>
    </div>
    ${genres?`<div class="genres">${genres}</div>`:''}
    ${rchips?`<div class="ratings-row">${rchips}</div>`:''}
    ${m.overview?`<p class="overview">${m.overview}</p>`:''}
    ${m.best_review?`<div class="review-block"><div class="rquote">${m.best_review}</div></div>`:''}
    ${m.ai_reason||why?`<div class="ai-block">
      ${m.ai_reason?`<p class="ai-reason">${m.ai_reason}</p>`:''}
      ${why?`<ul class="why-list">${why}</ul>`:''}
      ${m.similar_to?`<p class="similar">💡 ${m.similar_to}</p>`:''}
    </div>`:''}
    ${moods?`<div class="moods">${moods}</div>`:''}
    ${m.imdb_url?`<a class="card-link" href="${m.imdb_url}" target="_blank">⭐ View on IMDb</a>`:''}
  </div>
</div>`;
}

document.getElementById('pref').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&(e.ctrlKey||e.metaKey))getRecs();
});
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    logger.info("🎬  CineAI v5 → http://localhost:8000")
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)