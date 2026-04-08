"""
CineAI v6 — Smart Movie Recommendation Engine
==============================================
Features:
  • Smart recommendation by mood/genre/preference
  • Movie name search → full details, ratings, reviews, platforms
  • Actor search → filmography + bio
  • Character search → similar characters across movies
  • Advanced filters: year, language, IMDb, RT, Metacritic
  • Real movie posters (OMDb → TMDB → gradient fallback)
  • Watch platforms in India (TMDB)
  • Critics + public reviews (TMDB)
  • Auto-refreshing trending section
  • Token-efficient prompts (Groq free-tier safe)
  • Ollama/Mistral local LLM fallback
  • OWASP-aligned security: rate limiting, input sanitization, output escaping
"""

from __future__ import annotations

import asyncio
import html
import hashlib
import json
import logging
import re
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

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
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    preference: str = Field(..., min_length=1, max_length=settings.max_input_chars)
    watched: Optional[str] = Field(default="", max_length=settings.max_input_chars)
    count: StrictInt = Field(default=6, ge=1, le=10)
    genres: Optional[str] = Field(default="", max_length=settings.max_input_chars)
    hero_actor: Optional[str] = Field(default="", max_length=settings.max_input_chars)
    character_ref: Optional[str] = Field(default="", max_length=settings.max_input_chars)
    content_types: Optional[str] = Field(default="movie", max_length=settings.max_input_chars)
    search_mode: Literal["recommend", "movie", "actor", "character", "timeline"] = "recommend"
    language: Optional[str] = Field(default="", max_length=40)
    year_from: Optional[StrictInt] = Field(default=None, ge=1900, le=2100)
    year_to: Optional[StrictInt] = Field(default=None, ge=1900, le=2100)
    min_imdb: Optional[float] = Field(default=None, ge=0, le=10)
    min_rotten_tomatoes: Optional[StrictInt] = Field(default=None, ge=0, le=100)
    min_metacritic: Optional[StrictInt] = Field(default=None, ge=0, le=100)

    @field_validator("preference", "watched", "genres", "hero_actor", "character_ref", "content_types", "language")
    @classmethod
    def validate_and_sanitize_text(cls, value: Optional[str]) -> str:
        if value is None:
            return ""
        cleaned = value.strip()
        if len(cleaned) > settings.max_input_chars:
            raise ValueError(f"Input exceeds {settings.max_input_chars} characters")
        suspicious = ["<script", "</script", "javascript:", "onerror=", "onload=", "<iframe", "</iframe"]
        if any(token in cleaned.lower() for token in suspicious):
            raise ValueError("Unsafe input pattern detected")
        return cleaned


class MovieRatings(BaseModel):
    imdb: Optional[str] = None
    imdb_votes: Optional[str] = None
    rotten_tomatoes: Optional[str] = None
    metacritic: Optional[str] = None


class ReviewItem(BaseModel):
    author: Optional[str] = None
    content: Optional[str] = None
    rating: Optional[str] = None
    source: Optional[str] = None  # "critic" or "audience"


class MovieCard(BaseModel):
    rank: int
    title: str
    content_type: str = "movie"
    year: Optional[int] = None
    end_year: Optional[int] = None
    overview: Optional[str] = None
    genres: list[str] = []
    director: Optional[str] = None
    creator: Optional[str] = None
    cast: list[str] = []
    runtime: Optional[str] = None
    seasons: Optional[int] = None
    language: Optional[str] = None
    country: Optional[str] = None
    awards: Optional[str] = None
    ratings: MovieRatings = MovieRatings()
    poster_url: Optional[str] = None
    imdb_id: Optional[str] = None
    imdb_url: Optional[str] = None
    confidence: float = 0.0
    ai_reason: str = ""
    why_matches: list[str] = []
    mood_tags: list[str] = []
    similar_to: Optional[str] = None
    similar_titles: list[str] = []
    best_review: Optional[str] = None
    critics_reviews: list[ReviewItem] = []
    audience_reviews: list[ReviewItem] = []
    watch_platforms_in: list[str] = []
    watch_provider_links: list[dict[str, str]] = []
    combined_score: Optional[float] = None
    llm_source: str = "groq"
    # For actor search
    actor_bio: Optional[str] = None
    known_for: list[str] = []
    # For character search
    character_name: Optional[str] = None
    similar_characters: list[str] = []
    youtube_url: Optional[str] = None


class RecommendationResponse(BaseModel):
    status: str
    query_analysis: str = ""
    recommendations: list[MovieCard] = []
    total_results: int = 0
    execution_time_ms: float = 0.0
    sources_used: list[str] = []
    llm_used: str = "groq"
    search_mode: str = "recommend"


class HealthResponse(BaseModel):
    status: str
    version: str
    groq_configured: bool
    omdb_configured: bool
    tmdb_configured: bool
    ollama_available: bool
    timestamp: str


class TrendingResponse(BaseModel):
    movies: list[dict] = []
    series: list[dict] = []
    updated_at: str = ""


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    title_1: str = Field(..., min_length=1, max_length=settings.max_input_chars)
    title_2: str = Field(..., min_length=1, max_length=settings.max_input_chars)


class WatchlistItem(BaseModel):
    title: str
    imdb_id: Optional[str] = None
    poster_url: Optional[str] = None
    watch_platforms_in: list[str] = []
    new_platforms_in: list[str] = []
    last_checked_at: str


class WatchlistAddRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    title: str = Field(..., min_length=1, max_length=settings.max_input_chars)


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem] = []
    alerts: list[str] = []


def _safe_text(value: Optional[str], limit: int = 397) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()[:limit]
    return html.escape(text, quote=True)


def _safe_list(items: Optional[list], max_items: int = 8, item_limit: int = 80) -> list:
    if not items:
        return []
    result = []
    for i in items[:max_items]:
        if isinstance(i, str) and i.strip():
            result.append(_safe_text(i, limit=item_limit) or "")
        elif isinstance(i, dict):
            result.append(i)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════

class InMemoryRateLimiter:
    def __init__(self):
        self._store: dict[str, deque] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            q = self._store.setdefault(key, deque())
            cutoff = now - window_seconds
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= limit:
                retry_after = max(1, int(window_seconds - (now - q[0])))
                return False, retry_after
            q.append(now)
            return True, 0


rate_limiter = InMemoryRateLimiter()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "").strip()
    if fwd:
        return fwd.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def _enforce_rate_limits(request: Request) -> None:
    ip_key = f"ip:{_client_ip(request)}"
    ip_ok, ip_retry = rate_limiter.check(ip_key, settings.rate_limit_ip_max_requests, settings.rate_limit_ip_window_seconds)
    if not ip_ok:
        raise HTTPException(status_code=429, detail={"error": "rate_limit_exceeded", "retry_after_seconds": ip_retry}, headers={"Retry-After": str(ip_retry)})


# ═══════════════════════════════════════════════════════════════════════════
# LLM MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class LLMManager:
    GROQ_RATE_ERRORS = (413, 429, "rate_limit_exceeded", "Request too large")

    def __init__(self):
        self._groq: Optional[ChatGroq] = None
        self._ollama: Optional[ChatOllama] = None
        self._groq_failed_until: float = 0.0
        self._ollama_ok: Optional[bool] = None

    def _get_groq(self) -> Optional[ChatGroq]:
        if not settings.groq_api_key:
            return None
        if not self._groq:
            self._groq = ChatGroq(
                api_key=settings.groq_api_key,
                model_name=settings.groq_model,
                temperature=0.25,
                max_tokens=800,
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
        logger.warning(f"Groq rate-limited → backoff {seconds}s")

    def is_rate_error(self, exc: Exception) -> bool:
        return any(e in str(exc) for e in self.GROQ_RATE_ERRORS)

    async def invoke(self, chain_factory, kwargs: dict) -> tuple[str, str]:
        if not self.groq_in_backoff():
            groq = self._get_groq()
            if groq:
                try:
                    chain = chain_factory(groq)
                    result = await chain.ainvoke(kwargs)
                    return result, "groq"
                except Exception as exc:
                    if self.is_rate_error(exc):
                        self.mark_groq_failed(90)
                    else:
                        raise

        ollama = self._get_ollama()
        if ollama:
            try:
                chain = chain_factory(ollama)
                result = await chain.ainvoke(kwargs)
                return result, f"ollama/{settings.ollama_model}"
            except Exception as exc:
                raise RuntimeError(f"Both LLMs failed. Last error: {exc}")

        raise RuntimeError("No LLM available. Configure GROQ_API_KEY or run Ollama.")


llm_manager = LLMManager()


# ═══════════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════════

INTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Film expert. Extract intent as JSON only (no markdown):
{{"genres":[],"moods":[],"themes":[],"language":null,"hero_actor":null,"avoid":[],"titles":["T1","T2","T3","T4","T5","T6","T7","T8"],"summary":"one sentence"}}
titles: 8 real movie/show titles matching request. Include regional films if language specified."""),
    ("human", "Want: {preference}\nSeen: {watched}\nGenres: {genres}\nActor: {hero_actor}\nFranchise: {character_ref}\nTypes: {content_types}\nLanguage: {language}"),
])

RERANK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Film critic AI. Pick best {count} from candidates. JSON array only:
[{{"title":"exact match","confidence":0.9,"ai_reason":"2 sentences why","why_matches":["r1","r2","r3"],"mood_tags":["t1","t2"],"similar_to":"if you liked X","best_review":"one compelling sentence"}}]
Prioritize relevance to user query/genre/mood first, then ratings. Only use titles from candidates list."""),
    ("human", "Intent: {intent}\nCandidates:\n{candidates}"),
])

ACTOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Film expert. For the actor, return JSON only:
{{"bio":"2 sentence bio","known_for":["Movie1","Movie2","Movie3","Movie4","Movie5"],"style":"acting style description","best_films":["Film1","Film2","Film3","Film4","Film5","Film6"]}}"""),
    ("human", "Actor: {actor_name}"),
])

CHARACTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Film expert. Find movies with characters similar to the given character. JSON only:
{{"similar_characters":[{{"character":"CharName","movie":"MovieTitle","year":2020,"similarity":"why similar","actor":"ActorName"}}],"summary":"one sentence about the archetype"}}
Return 6 similar characters from different movies."""),
    ("human", "Character/Franchise: {character_name}"),
])

FALLBACK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Recommend {count} films. JSON array only:
[{{"title":"","year":2020,"content_type":"movie","genres":[],"director":"","cast":[],"ai_reason":"","why_matches":[],"confidence":0.8,"mood_tags":[],"similar_to":"","best_review":""}}]"""),
    ("human", "{preference}"),
])

SIMILARITY_PROMPT_ENHANCED = ChatPromptTemplate.from_messages([
    ("system", """Film expert. Given the reference film below, recommend {count} films with SIMILAR:
- Genre and emotional tone
- Story themes and narrative arc
- Character dynamics and relationships
- Period/setting if relevant

Return JSON array only (no markdown):
[{{"title":"exact movie name","year":2020,"similarity_reason":"2 sentences explaining thematic/emotional connection"}}]

Focus on thematic and emotional similarity, NOT just surface-level genre matching."""),
    ("human", "Reference Film: {title}\nGenres: {genres}\nOverview: {overview}\nKey themes: {themes}"),
])


# ═══════════════════════════════════════════════════════════════════════════
# MEDIA CLIENT
# ═══════════════════════════════════════════════════════════════════════════

class MediaClient:
    OMDB = "https://www.omdbapi.com"
    TMDB_SEARCH = "https://api.themoviedb.org/3/search/multi"
    TMDB_IMG = "https://image.tmdb.org/t/p/w500"
    TMDB_FIND = "https://api.themoviedb.org/3/find"
    TMDB_TRENDING = "https://api.themoviedb.org/3/trending"
    TMDB_PERSON = "https://api.themoviedb.org/3/search/person"

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=10, follow_redirects=True)

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

    async def by_title(self, title: str, media_type: Optional[str] = None) -> dict:
        if media_type:
            d = await self._omdb_fetch({"t": title, "plot": "full", "type": media_type})
            if d:
                return d
        for t in ("movie", "series"):
            d = await self._omdb_fetch({"t": title, "plot": "full", "type": t})
            if d:
                return d
        return {}

    async def by_imdb_id(self, imdb_id: str) -> dict:
        if not imdb_id:
            return {}
        return await self._omdb_fetch({"i": imdb_id, "plot": "full"})

    async def search(self, query: str, page: int = 1) -> list[dict]:
        d = await self._omdb_fetch({"s": query, "page": page})
        return d.get("Search", []) if d else []

    async def _tmdb_poster(self, title: str, year: Optional[int] = None) -> Optional[str]:
        if not settings.tmdb_api_key:
            return None
        try:
            params = {"api_key": settings.tmdb_api_key, "query": title}
            if year:
                params["year"] = year
            r = await self._client.get(self.TMDB_SEARCH, params=params)
            for item in r.json().get("results", [])[:3]:
                path = item.get("poster_path")
                if path:
                    return f"{self.TMDB_IMG}{path}"
        except Exception:
            pass
        return None

    async def _tmdb_find_by_imdb(self, imdb_id: str) -> tuple[Optional[str], Optional[int]]:
        if not settings.tmdb_api_key or not imdb_id:
            return None, None
        try:
            r = await self._client.get(
                f"{self.TMDB_FIND}/{imdb_id}",
                params={"api_key": settings.tmdb_api_key, "external_source": "imdb_id"},
            )
            data = r.json()
            if data.get("movie_results"):
                return "movie", data["movie_results"][0].get("id")
            if data.get("tv_results"):
                return "tv", data["tv_results"][0].get("id")
        except Exception:
            pass
        return None, None

    async def watch_providers_in(self, imdb_id: Optional[str]) -> list[str]:
        if not imdb_id or not settings.tmdb_api_key:
            return []
        media_type, tmdb_id = await self._tmdb_find_by_imdb(imdb_id)
        if not media_type or not tmdb_id:
            return []
        try:
            r = await self._client.get(
                f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/watch/providers",
                params={"api_key": settings.tmdb_api_key},
            )
            in_data = r.json().get("results", {}).get("IN", {})
            providers: list[str] = []
            for section in ("flatrate", "free", "ads", "rent", "buy"):
                for p in in_data.get(section, []):
                    name = p.get("provider_name")
                    if name and name not in providers:
                        providers.append(name)
            return providers[:8]
        except Exception:
            return []

    async def watch_provider_payload_in(self, imdb_id: Optional[str]) -> tuple[list[str], list[dict[str, str]]]:
        """
        Return provider names plus clickable India watch URL if TMDB exposes it.
        """
        if not imdb_id or not settings.tmdb_api_key:
            return [], []
        media_type, tmdb_id = await self._tmdb_find_by_imdb(imdb_id)
        if not media_type or not tmdb_id:
            return [], []
        try:
            r = await self._client.get(
                f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/watch/providers",
                params={"api_key": settings.tmdb_api_key},
            )
            in_data = r.json().get("results", {}).get("IN", {})
            providers: list[str] = []
            links: list[dict[str, str]] = []
            link_url = in_data.get("link") or ""
            for section in ("flatrate", "free", "ads", "rent", "buy"):
                for p in in_data.get(section, []):
                    name = p.get("provider_name")
                    if not name or name in providers:
                        continue
                    providers.append(name)
                    links.append({"name": name, "url": link_url})
            return providers[:8], links[:8]
        except Exception:
            return [], []

    async def get_reviews(self, imdb_id: Optional[str]) -> tuple[list[ReviewItem], list[ReviewItem]]:
        """Return (critics_reviews, audience_reviews) as structured items."""
        if not imdb_id or not settings.tmdb_api_key:
            return [], []
        media_type, tmdb_id = await self._tmdb_find_by_imdb(imdb_id)
        if not media_type or not tmdb_id:
            return [], []
        try:
            r = await self._client.get(
                f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/reviews",
                params={"api_key": settings.tmdb_api_key, "page": 1},
            )
            results = r.json().get("results", [])
            critics, audience = [], []
            for rv in results[:12]:
                author = (rv.get("author") or "")
                content = (rv.get("content") or "").strip().replace("\n", " ")
                if not content:
                    continue
                # Get rating from author_details
                rating = None
                ad = rv.get("author_details", {})
                if ad.get("rating"):
                    rating = str(ad["rating"])
                item = ReviewItem(
                    author=author[:60],
                    content=content[:300],
                    rating=rating,
                    source="critic" if any(x in author.lower() for x in ("critic", "editor", "magazine", "review", "press")) else "audience"
                )
                if item.source == "critic" and len(critics) < 3:
                    critics.append(item)
                elif item.source == "audience" and len(audience) < 3:
                    audience.append(item)
                else:
                    if len(audience) < 3:
                        audience.append(item)
            return critics, audience
        except Exception:
            return [], []

    async def get_trending(self) -> dict:
        """Get trending movies and series from TMDB."""
        if not settings.tmdb_api_key:
            return {"movies": [], "series": []}
        try:
            movies_r, series_r = await asyncio.gather(
                self._client.get(f"{self.TMDB_TRENDING}/movie/week", params={"api_key": settings.tmdb_api_key}),
                self._client.get(f"{self.TMDB_TRENDING}/tv/week", params={"api_key": settings.tmdb_api_key}),
            )
            movies = []
            for m in movies_r.json().get("results", [])[:8]:
                movies.append({
                    "title": m.get("title", ""),
                    "year": str(m.get("release_date", ""))[:4],
                    "poster": f"{self.TMDB_IMG}{m['poster_path']}" if m.get("poster_path") else None,
                    "rating": m.get("vote_average"),
                    "overview": (m.get("overview") or "")[:120],
                    "tmdb_id": m.get("id"),
                })
            series = []
            for s in series_r.json().get("results", [])[:8]:
                series.append({
                    "title": s.get("name", ""),
                    "year": str(s.get("first_air_date", ""))[:4],
                    "poster": f"{self.TMDB_IMG}{s['poster_path']}" if s.get("poster_path") else None,
                    "rating": s.get("vote_average"),
                    "overview": (s.get("overview") or "")[:120],
                    "tmdb_id": s.get("id"),
                })
            return {"movies": movies, "series": series}
        except Exception as e:
            logger.warning(f"Trending fetch failed: {e}")
            return {"movies": [], "series": []}

    async def search_person(self, name: str) -> Optional[dict]:
        """Search for a person (actor/director) on TMDB."""
        if not settings.tmdb_api_key:
            return None
        try:
            r = await self._client.get(
                self.TMDB_PERSON,
                params={"api_key": settings.tmdb_api_key, "query": name},
            )
            results = r.json().get("results", [])
            if not results:
                return None
            person = results[0]
            pid = person.get("id")
            if not pid:
                return None
            # Get person details + credits
            details_r, credits_r = await asyncio.gather(
                self._client.get(f"https://api.themoviedb.org/3/person/{pid}", params={"api_key": settings.tmdb_api_key}),
                self._client.get(f"https://api.themoviedb.org/3/person/{pid}/combined_credits", params={"api_key": settings.tmdb_api_key}),
            )
            details = details_r.json()
            credits = credits_r.json()
            known_for = []
            cast_credits = sorted(credits.get("cast", []), key=lambda x: x.get("popularity", 0), reverse=True)
            for c in cast_credits[:10]:
                title = c.get("title") or c.get("name", "")
                if title:
                    known_for.append(title)
            profile_path = person.get("profile_path") or details.get("profile_path")
            return {
                "name": person.get("name", name),
                "bio": (details.get("biography") or "")[:400],
                "known_for": known_for[:6],
                "profile_img": f"{self.TMDB_IMG}{profile_path}" if profile_path else None,
                "birthday": details.get("birthday"),
                "place_of_birth": details.get("place_of_birth"),
            }
        except Exception as e:
            logger.warning(f"Person search failed: {e}")
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
            results = await self.search(title)
            if results:
                imdb_id = results[0].get("imdbID")
                if imdb_id:
                    data = await self._omdb_fetch({"i": imdb_id, "plot": "full"})
        if not data:
            return None
        return await self._build_enriched(title, data)

    async def enrich_by_imdb_id(self, imdb_id: str, fallback_title: str = "") -> Optional[dict]:
        data = await self.by_imdb_id(imdb_id)
        if not data:
            return None
        return await self._build_enriched(fallback_title or data.get("Title", ""), data)

    async def _build_enriched(self, title: str, data: dict) -> Optional[dict]:
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

        imdb_id = data.get("imdbID") or None
        if imdb_id:
            (platforms, provider_links), (critics_reviews, audience_reviews) = await asyncio.gather(
                self.watch_provider_payload_in(imdb_id),
                self.get_reviews(imdb_id),
            )
        else:
            platforms = []
            provider_links = []
            critics_reviews = []
            audience_reviews = []

        seasons_str = data.get("totalSeasons", "")
        writer = (data.get("Writer") or "").strip()
        return {
            "title": data.get("Title", title),
            "content_type": ct,
            "year": year,
            "end_year": end_year,
            "overview": (data.get("Plot") or "").strip() or None,
            "genres": [g.strip() for g in data.get("Genre", "").split(",") if g.strip()],
            "director": (data.get("Director") or "").strip() or None,
            "creator": writer if ct == "series" else None,
            "cast": [a.strip() for a in data.get("Actors", "").split(",") if a.strip()][:5],
            "runtime": (data.get("Runtime") or "").strip() or None,
            "seasons": int(seasons_str) if seasons_str and seasons_str.isdigit() else None,
            "language": (data.get("Language") or "").split(",")[0].strip() or None,
            "country": (data.get("Country") or "").strip() or None,
            "awards": (data.get("Awards") or "").strip() or None,
            "imdb_id": imdb_id,
            "imdb_rating": data.get("imdbRating") or None,
            "imdb_votes": data.get("imdbVotes") or None,
            "rt": self.extract_rating(data, "Rotten Tomatoes"),
            "metacritic": self.extract_rating(data, "Metacritic"),
            "platforms_in": platforms,
            "provider_links_in": provider_links,
            "critics_reviews": critics_reviews,
            "audience_reviews": audience_reviews,
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
            self._key(raw).write_text(json.dumps(value, default=str))
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
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text)
        for pattern in (r"\[[\s\S]*\]", r"\{[\s\S]*\}"):
            m = re.search(pattern, text)
            if m:
                try:
                    return json.loads(m.group())
                except Exception:
                    pass
        return fallback

    def _compact_candidates(self, enriched: list[dict]) -> str:
        lines = []
        for e in enriched:
            score = f" score={e['combined_score']}" if e.get("combined_score") else ""
            rel = f" rel={e['relevance_score']}" if e.get("relevance_score") is not None else ""
            imdb = f" imdb={e['imdb_rating']}" if e.get("imdb_rating") else ""
            rt = f" rt={e['rt']}" if e.get("rt") else ""
            lines.append(f"- {e['title']} ({e.get('year','?')}){score}{rel}{imdb}{rt} | {(e.get('overview') or '')[:80]}")
        return "\n".join(lines)

    def _passes_filters(self, req: RecommendationRequest, item: dict) -> bool:
        if req.year_from and (not item.get("year") or item["year"] < req.year_from):
            return False
        if req.year_to and (not item.get("year") or item["year"] > req.year_to):
            return False
        if req.language:
            lang = (item.get("language") or "").lower()
            if req.language.lower() not in lang:
                return False
        if req.min_imdb is not None:
            try:
                if float(item.get("imdb_rating") or 0) < req.min_imdb:
                    return False
            except Exception:
                return False
        if req.min_rotten_tomatoes is not None:
            try:
                rt_val = int(str(item.get("rt") or "").replace("%", ""))
                if rt_val < req.min_rotten_tomatoes:
                    return False
            except Exception:
                return False
        if req.min_metacritic is not None:
            try:
                mc_val = int(str(item.get("metacritic") or "").split("/")[0])
                if mc_val < req.min_metacritic:
                    return False
            except Exception:
                return False
        return True

    def _intent_terms(self, req: RecommendationRequest, intent_data: dict) -> set[str]:
        parts = [
            req.preference or "",
            req.genres or "",
            req.hero_actor or "",
            req.character_ref or "",
            " ".join(intent_data.get("genres", []) or []),
            " ".join(intent_data.get("moods", []) or []),
            " ".join(intent_data.get("themes", []) or []),
        ]
        tokens: set[str] = set()
        for part in parts:
            for tok in re.split(r"[^a-z0-9]+", part.lower()):
                if len(tok) >= 3:
                    tokens.add(tok)
        return tokens

    def _relevance_score(self, req: RecommendationRequest, intent_data: dict, item: dict) -> float:
        terms = self._intent_terms(req, intent_data)
        if not terms:
            return 50.0
        concept_map = {
            "love": {"romance", "romantic", "relationship", "couple"},
            "romance": {"love", "romantic", "relationship", "couple"},
            "romantic": {"romance", "love", "relationship"},
            "funny": {"comedy", "humor", "humour"},
            "sad": {"drama", "emotional"},
            "scary": {"horror", "thriller"},
            "detective": {"mystery", "crime", "thriller"},
            "space": {"sci", "scifi", "science", "fiction"},
            "family": {"family", "kids", "children"},
        }
        expanded = set(terms)
        for t in list(terms):
            expanded.update(concept_map.get(t, set()))

        hay = " ".join([
            item.get("title", ""),
            item.get("overview", "") or "",
            " ".join(item.get("genres", []) or []),
            " ".join(item.get("cast", []) or []),
            item.get("director", "") or "",
            item.get("language", "") or "",
        ]).lower()
        hay_tokens = {t for t in re.split(r"[^a-z0-9]+", hay) if len(t) >= 3}
        token_overlap = len(expanded & hay_tokens) / max(1, len(expanded))

        item_genres = {g.strip().lower() for g in item.get("genres", []) if g}
        wanted = {g.strip().lower() for g in (intent_data.get("genres", []) or []) if g}
        wanted.update({g.strip().lower() for g in (req.genres or "").split(",") if g.strip()})
        genre_overlap = len(wanted & item_genres) / max(1, len(wanted)) if wanted else 0.0

        romance_trigger = any(t in expanded for t in ("love", "romance", "romantic", "relationship", "couple"))
        romance_boost = 0.20 if romance_trigger and "romance" in item_genres else 0.0
        raw = (token_overlap * 0.45) + (genre_overlap * 0.45) + romance_boost
        return round(min(1.0, raw) * 100, 1)

    def _extract_similarity_anchor(self, text: str) -> Optional[str]:
        q = (text or "").strip()
        if not q:
            return None
        patterns = [
            r"(?:similar\s+(?:movies|films|shows|series)?\s*(?:like|to)\s+)(.+)$",
            r"(?:movies?\s+like\s+)(.+)$",
            r"(?:films?\s+like\s+)(.+)$",
            r"(?:like\s+)(.+)$",
        ]
        low = q.lower()
        for p in patterns:
            m = re.search(p, low, flags=re.IGNORECASE)
            if m:
                anchor = q[m.start(1):m.end(1)].strip(" .,:;!?\"'")
                return anchor if anchor else None
        return None

    def _extract_key_themes(self, overview: str) -> str:
        if not overview:
            return ""
        thematic_keywords = {
            "love", "romance", "war", "family", "revenge", "sacrifice", "journey", "destiny",
            "loss", "grief", "hope", "friendship", "loyalty", "betrayal", "duty", "honor",
            "emotional", "period", "historical", "soldier", "officer", "separation", "reunion",
        }
        tokens = {t for t in re.split(r"[^a-z0-9]+", overview.lower()) if len(t) > 3}
        themes = tokens & thematic_keywords
        return ", ".join(sorted(themes)[:5]) if themes else "drama"

    def _anchor_similarity(self, anchor: dict, item: dict) -> float:
        """
        Enhanced similarity scoring focusing on genre, story themes, and emotional tone.
        Returns a score from 0-100.
        """
        a_genres = {g.lower() for g in anchor.get("genres", [])}
        i_genres = {g.lower() for g in item.get("genres", [])}
        genre_overlap = len(a_genres & i_genres) / max(1, len(a_genres)) if a_genres else 0.0
        genre_bonus = 0.15 if genre_overlap > 0 else 0.0

        a_text = (anchor.get("overview", "") or "").lower()
        i_text = (item.get("overview", "") or "").lower()
        a_tokens = {t for t in re.split(r"[^a-z0-9]+", a_text) if len(t) > 3}
        i_tokens = {t for t in re.split(r"[^a-z0-9]+", i_text) if len(t) > 3}

        emotional_keywords = {
            "love", "romance", "romantic", "relationship", "emotional", "heart", "war", "battle",
            "sacrifice", "duty", "honor", "family", "revenge", "journey", "destiny", "loss",
            "grief", "hope", "tragedy", "death", "friendship", "loyalty", "betrayal", "separation",
            "reunion", "pain", "memory", "past", "nostalgia", "longing", "devotion", "period",
            "soldier", "officer", "historical", "epic", "drama", "beautiful",
        }
        a_emotional = a_tokens & emotional_keywords
        i_emotional = i_tokens & emotional_keywords
        emotional_overlap = len(a_emotional & i_emotional) / max(1, len(a_emotional)) if a_emotional else 0.0
        token_overlap = len(a_tokens & i_tokens) / max(1, len(a_tokens)) if a_tokens else 0.0

        year_score = 0.0
        if anchor.get("year") and item.get("year"):
            year_diff = abs(anchor["year"] - item["year"])
            if year_diff <= 3:
                year_score = 0.05
            elif year_diff <= 10:
                year_score = 0.03

        lang_bonus = 0.0
        if anchor.get("language") and item.get("language"):
            if str(anchor["language"]).lower() == str(item["language"]).lower():
                lang_bonus = 0.05

        raw_score = (
            genre_overlap * 0.45 +
            emotional_overlap * 0.25 +
            token_overlap * 0.15 +
            genre_bonus +
            year_score +
            lang_bonus
        )
        return round(min(1.0, raw_score) * 100, 1)

    async def _handle_similarity_query(self, req: RecommendationRequest, anchor_title: str) -> RecommendationResponse:
        t0 = time.time()
        anchor = await self.media.enrich(anchor_title)
        if not anchor:
            s = await self.media.search(anchor_title)
            if s:
                anchor = await self.media.enrich_by_imdb_id(s[0].get("imdbID", ""), anchor_title)
        if not anchor:
            raise HTTPException(status_code=404, detail=f"Movie '{anchor_title}' not found.")

        similar_titles: list[str] = []
        llm_used = "none"
        try:
            raw, llm_used = await llm_manager.invoke(
                lambda llm: SIMILARITY_PROMPT_ENHANCED | llm | StrOutputParser(),
                {
                    "title": anchor.get("title", ""),
                    "genres": ", ".join(anchor.get("genres", []))[:120],
                    "overview": (anchor.get("overview") or "")[:220],
                    "themes": self._extract_key_themes(anchor.get("overview", "") or ""),
                    "count": max(req.count*2, 8),
                },
            )
            parsed = self._parse_json(raw, [])
            similar_titles = [x.get("title", "").strip() for x in parsed if isinstance(x, dict) and x.get("title")]
        except Exception:
            similar_titles = []

        # Safety net: add a few title-based search seeds if LLM returns sparse output.
        if len(similar_titles) < req.count:
            seeds = await self.media.search(f"{anchor.get('title','')} movie")
            similar_titles.extend([x.get("Title", "") for x in seeds[:8] if x.get("Title")])

        results = await asyncio.gather(*[self.media.enrich(t) for t in similar_titles[:20]], return_exceptions=True)
        enriched: list[dict] = []
        seen: set[str] = set()
        anchor_iid = anchor.get("imdb_id")
        MIN_SIMILARITY = settings.similarity_min_threshold
        for r in results:
            if not r or isinstance(r, Exception):
                continue
            iid = r.get("imdb_id") or ""
            title_l = r.get("title", "").lower()
            if iid and iid == anchor_iid:
                continue
            if title_l in seen:
                continue
            seen.add(title_l)
            sim = self._anchor_similarity(anchor, r)
            if sim < MIN_SIMILARITY:
                continue
            quality = r.get("combined_score") or 0.0
            r["similarity_score"] = sim
            r["rank_score"] = round(sim * 0.80 + quality * 0.20, 2)
            enriched.append(r)
        enriched.sort(key=lambda x: (x.get("rank_score") or 0), reverse=True)

        final: list[MovieCard] = []
        for i, e in enumerate(enriched[:req.count], 1):
            iid = e.get("imdb_id") or ""
            critics_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in e.get("critics_reviews", [])]
            audience_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in e.get("audience_reviews", [])]
            final.append(MovieCard(
                rank=i, title=e["title"], content_type=e.get("content_type", "movie"),
                year=e.get("year"), end_year=e.get("end_year"), overview=e.get("overview"),
                genres=e.get("genres", []), director=e.get("director"), creator=e.get("creator"),
                cast=e.get("cast", []), runtime=e.get("runtime"), seasons=e.get("seasons"),
                language=e.get("language"), country=e.get("country"), awards=e.get("awards"),
                ratings=MovieRatings(
                    imdb=e.get("imdb_rating"), imdb_votes=e.get("imdb_votes"),
                    rotten_tomatoes=e.get("rt"), metacritic=e.get("metacritic"),
                ),
                poster_url=e.get("poster"), imdb_id=iid or None,
                imdb_url=f"https://www.imdb.com/title/{iid}/" if iid else None,
                confidence=min(0.95, max(0.7, (e.get("similarity_score", 70) / 100))),
                ai_reason=f"Matched to {anchor.get('title')} by genre/story/emotional tone.",
                watch_platforms_in=e.get("platforms_in", []),
                watch_provider_links=e.get("provider_links_in", []),
                critics_reviews=critics_r, audience_reviews=audience_r,
                combined_score=e.get("combined_score"), llm_source=llm_used,
            ))

        return RecommendationResponse(
            status="success",
            query_analysis=f"Movies similar to {anchor.get('title')} by genre, story and emotional tone.",
            recommendations=final,
            total_results=len(final),
            execution_time_ms=round((time.time() - t0) * 1000, 1),
            sources_used=["Similarity Intent", "OMDb/IMDb", "TMDB", f"LLM ({llm_used})"],
            llm_used=llm_used,
            search_mode="recommend",
        )

    async def _seed_titles(self, req: RecommendationRequest, llm_titles: list[str]) -> list[tuple[str, Optional[str]]]:
        seeds: list[tuple[str, Optional[str]]] = []
        seen_titles: set[str] = set()
        seen_ids: set[str] = set()

        def add(title: Optional[str], imdb_id: Optional[str] = None):
            if not title:
                return
            t = str(title).strip()
            key = t.lower()
            iid = (imdb_id or "").strip()
            if (iid and iid in seen_ids) or key in seen_titles:
                return
            seen_titles.add(key)
            if iid:
                seen_ids.add(iid)
            seeds.append((t, iid or None))

        for t in llm_titles[:12]:
            add(t)

        queries = [req.preference]
        if req.hero_actor:
            queries.append(req.hero_actor)
        if req.genres:
            queries.append(req.genres)
        if req.character_ref:
            queries.append(req.character_ref)

        for q in queries[:4]:
            try:
                for hit in (await self.media.search(q[:120]))[:10]:
                    add(hit.get("Title"), hit.get("imdbID"))
            except Exception:
                pass

        return seeds[:28]

    async def _handle_actor_search(self, req: RecommendationRequest) -> RecommendationResponse:
        """Special handling for actor name searches."""
        t0 = time.time()
        actor_name = req.preference

        # Get actor info from TMDB
        person_data = await self.media.search_person(actor_name)

        # Get LLM bio and filmography
        try:
            raw, llm_used = await llm_manager.invoke(
                lambda llm: ACTOR_PROMPT | llm | StrOutputParser(),
                {"actor_name": actor_name[:100]}
            )
            actor_info = self._parse_json(raw, {})
        except Exception:
            actor_info = {}
            llm_used = "none"

        bio = (person_data or {}).get("bio") or actor_info.get("bio", "")
        known_for_titles = (person_data or {}).get("known_for") or actor_info.get("best_films", [])

        # Enrich known films
        enriched = []
        seen_iids: set[str] = set()
        tasks = [self.media.enrich(t) for t in known_for_titles[:8]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if r and not isinstance(r, Exception):
                iid = r.get("imdb_id") or ""
                if iid in seen_iids:
                    continue
                if iid:
                    seen_iids.add(iid)
                enriched.append(r)

        cards = []
        for i, e in enumerate(enriched[:req.count], 1):
            iid = e.get("imdb_id") or ""
            critics_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in e.get("critics_reviews", [])]
            audience_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in e.get("audience_reviews", [])]
            cards.append(MovieCard(
                rank=i,
                title=e["title"],
                content_type=e.get("content_type", "movie"),
                year=e.get("year"),
                overview=e.get("overview"),
                genres=e.get("genres", []),
                director=e.get("director"),
                cast=e.get("cast", []),
                runtime=e.get("runtime"),
                language=e.get("language"),
                ratings=MovieRatings(
                    imdb=e.get("imdb_rating"),
                    imdb_votes=e.get("imdb_votes"),
                    rotten_tomatoes=e.get("rt"),
                    metacritic=e.get("metacritic"),
                ),
                poster_url=e.get("poster"),
                imdb_id=iid or None,
                imdb_url=f"https://www.imdb.com/title/{iid}/" if iid else None,
                confidence=0.9,
                ai_reason=f"Film featuring {actor_name}",
                watch_platforms_in=e.get("platforms_in", []),
                watch_provider_links=e.get("provider_links_in", []),
                combined_score=e.get("combined_score"),
                critics_reviews=critics_r,
                audience_reviews=audience_r,
                actor_bio=bio[:300] if i == 1 else None,
                known_for=actor_info.get("known_for", [])[:5] if i == 1 else [],
                llm_source=llm_used,
            ))

        return RecommendationResponse(
            status="success",
            query_analysis=f"Films featuring {actor_name}. {actor_info.get('style', '')}",
            recommendations=cards,
            total_results=len(cards),
            execution_time_ms=round((time.time() - t0) * 1000, 1),
            sources_used=["OMDb/IMDb", "TMDB"],
            llm_used=llm_used,
            search_mode="actor",
        )

    async def _handle_character_search(self, req: RecommendationRequest) -> RecommendationResponse:
        """Find movies with similar characters."""
        t0 = time.time()
        character_name = req.preference

        try:
            raw, llm_used = await llm_manager.invoke(
                lambda llm: CHARACTER_PROMPT | llm | StrOutputParser(),
                {"character_name": character_name[:100]}
            )
            char_data = self._parse_json(raw, {})
        except Exception:
            char_data = {}
            llm_used = "none"

        similar_chars = char_data.get("similar_characters", [])
        summary = char_data.get("summary", f"Characters similar to {character_name}")

        # Enrich each movie
        enriched_cards = []
        tasks = []
        for sc in similar_chars[:8]:
            movie_title = sc.get("movie", "")
            if movie_title:
                tasks.append((sc, self.media.enrich(movie_title)))

        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
        for i, (task_pair, result) in enumerate(zip(tasks, results)):
            sc, _ = task_pair
            e = result if result and not isinstance(result, Exception) else None
            movie_title = sc.get("movie", "")
            iid = (e or {}).get("imdb_id") or ""
            critics_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in (e or {}).get("critics_reviews", [])]
            audience_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in (e or {}).get("audience_reviews", [])]
            enriched_cards.append(MovieCard(
                rank=i + 1,
                title=(e or {}).get("title") or movie_title,
                content_type=(e or {}).get("content_type", "movie"),
                year=(e or {}).get("year"),
                overview=(e or {}).get("overview"),
                genres=(e or {}).get("genres", []),
                director=(e or {}).get("director"),
                cast=(e or {}).get("cast", []),
                ratings=MovieRatings(
                    imdb=(e or {}).get("imdb_rating"),
                    imdb_votes=(e or {}).get("imdb_votes"),
                    rotten_tomatoes=(e or {}).get("rt"),
                    metacritic=(e or {}).get("metacritic"),
                ),
                poster_url=(e or {}).get("poster"),
                imdb_id=iid or None,
                imdb_url=f"https://www.imdb.com/title/{iid}/" if iid else None,
                confidence=0.85,
                ai_reason=sc.get("similarity", ""),
                watch_platforms_in=(e or {}).get("platforms_in", []),
                watch_provider_links=(e or {}).get("provider_links_in", []),
                combined_score=(e or {}).get("combined_score"),
                critics_reviews=critics_r,
                audience_reviews=audience_r,
                character_name=sc.get("character"),
                similar_characters=[f"{sc.get('character')} played by {sc.get('actor', 'Unknown')}"],
                llm_source=llm_used,
            ))

        return RecommendationResponse(
            status="success",
            query_analysis=summary,
            recommendations=enriched_cards,
            total_results=len(enriched_cards),
            execution_time_ms=round((time.time() - t0) * 1000, 1),
            sources_used=["LLM (character analysis)", "OMDb/IMDb"],
            llm_used=llm_used,
            search_mode="character",
        )

    async def _handle_movie_lookup(self, req: RecommendationRequest) -> RecommendationResponse:
        """Direct movie name lookup — full details."""
        t0 = time.time()
        title = req.preference

        data = await self.media.enrich(title)
        if not data:
            # Fallback to search
            results = await self.media.search(title)
            if results:
                data = await self.media.enrich_by_imdb_id(results[0].get("imdbID", ""), title)

        if not data:
            raise HTTPException(status_code=404, detail=f"Movie '{title}' not found.")

        iid = data.get("imdb_id") or ""
        critics_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in data.get("critics_reviews", [])]
        audience_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in data.get("audience_reviews", [])]

        # Find similar movies using LLM
        similar_titles = []
        try:
            raw, llm_used = await llm_manager.invoke(
                lambda llm: FALLBACK_PROMPT | llm | StrOutputParser(),
                {"preference": f"Movies similar to {title}", "count": 5}
            )
            similar_data = self._parse_json(raw, [])
            similar_titles = [s.get("title", "") for s in similar_data[:5] if s.get("title")]
        except Exception:
            llm_used = "none"

        card = MovieCard(
            rank=1,
            title=data["title"],
            content_type=data.get("content_type", "movie"),
            year=data.get("year"),
            end_year=data.get("end_year"),
            overview=data.get("overview"),
            genres=data.get("genres", []),
            director=data.get("director"),
            creator=data.get("creator"),
            cast=data.get("cast", []),
            runtime=data.get("runtime"),
            seasons=data.get("seasons"),
            language=data.get("language"),
            country=data.get("country"),
            awards=data.get("awards"),
            ratings=MovieRatings(
                imdb=data.get("imdb_rating"),
                imdb_votes=data.get("imdb_votes"),
                rotten_tomatoes=data.get("rt"),
                metacritic=data.get("metacritic"),
            ),
            poster_url=data.get("poster"),
            imdb_id=iid or None,
            imdb_url=f"https://www.imdb.com/title/{iid}/" if iid else None,
            confidence=1.0,
            ai_reason="Direct movie lookup",
            watch_platforms_in=data.get("platforms_in", []),
            watch_provider_links=data.get("provider_links_in", []),
            combined_score=data.get("combined_score"),
            critics_reviews=critics_r,
            audience_reviews=audience_r,
            similar_to=", ".join(similar_titles[:3]) if similar_titles else None,
            similar_titles=similar_titles[:8],
            llm_source=llm_used,
        )

        return RecommendationResponse(
            status="success",
            query_analysis=f"Full details for: {data['title']}",
            recommendations=[card],
            total_results=1,
            execution_time_ms=round((time.time() - t0) * 1000, 1),
            sources_used=["OMDb/IMDb", "TMDB", "Interactive Similar/People"],
            llm_used=llm_used,
            search_mode="movie",
        )

    async def recommend(self, req: RecommendationRequest) -> RecommendationResponse:
        # Route to specialized handlers
        similar_anchor = self._extract_similarity_anchor(req.preference)
        if similar_anchor and req.search_mode == "recommend":
            return await self._handle_similarity_query(req, similar_anchor)
        if req.search_mode == "actor":
            return await self._handle_actor_search(req)
        if req.search_mode == "character":
            return await self._handle_character_search(req)
        if req.search_mode == "movie":
            return await self._handle_movie_lookup(req)
        if req.search_mode == "timeline":
            return await self._handle_mood_timeline(req)

        t0 = time.time()
        sources_used: list[str] = []
        llm_used = "groq"

        # Step 1: Intent extraction
        day_key = datetime.utcnow().strftime("%Y-%m-%d")
        cache_key = f"v6intent:{day_key}:{req.preference}:{req.watched}:{req.genres}:{req.hero_actor}:{req.character_ref}:{req.content_types}:{req.language}"
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
                        "language": (req.language or "any")[:30],
                    }
                )
                intent_data = self._parse_json(raw, {})
                self.cache.set(cache_key, intent_data)
            except Exception as exc:
                logger.error(f"Intent extraction failed: {exc}")
                intent_data = {"titles": [req.preference], "summary": req.preference}

        sources_used.append(f"LLM ({llm_used})")
        suggested_titles = [str(t).strip() for t in intent_data.get("titles", [req.preference]) if str(t).strip()]
        summary = intent_data.get("summary", req.preference)

        # Step 2: Parallel enrichment
        watched_lower = {w.strip().lower() for w in (req.watched or "").split(",") if w.strip()}

        async def enrich_cached(seed_title: str, seed_imdb_id: Optional[str]) -> Optional[dict]:
            ck = f"v6omdb:{(seed_imdb_id or seed_title).lower()}"
            cached = self.cache.get(ck)
            if cached is not None:
                return cached
            result = await (self.media.enrich_by_imdb_id(seed_imdb_id, seed_title) if seed_imdb_id else self.media.enrich(seed_title))
            if result:
                self.cache.set(ck, result)
            return result

        seed_pairs = await self._seed_titles(req, suggested_titles)
        raw_results = await asyncio.gather(*[enrich_cached(t, i) for t, i in seed_pairs], return_exceptions=True)

        enriched: list[dict] = []
        seen_titles: set[str] = set()
        seen_iids: set[str] = set()
        for r in raw_results:
            if not r or isinstance(r, Exception):
                continue
            key = r["title"].lower()
            iid = (r.get("imdb_id") or "").lower()
            if key in seen_titles or key in watched_lower:
                continue
            if iid and iid in seen_iids:
                continue
            seen_titles.add(key)
            if iid:
                seen_iids.add(iid)
            enriched.append(r)

        enriched = [item for item in enriched if self._passes_filters(req, item)]
        for item in enriched:
            rel = self._relevance_score(req, intent_data, item)
            quality = item.get("combined_score") or 0.0
            # Prioritize intent match over pure global quality.
            item["relevance_score"] = rel
            item["rank_score"] = round((rel * 0.7) + (quality * 0.3), 2)
        enriched.sort(key=lambda x: (x.get("rank_score") or 0, x.get("combined_score") or 0), reverse=True)

        if settings.omdb_api_key:
            sources_used.append("OMDb/IMDb")
        if settings.tmdb_api_key:
            sources_used.append("TMDB")

        # Step 3: Pure LLM fallback
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
                    search_mode="recommend",
                )
            except Exception as exc:
                raise HTTPException(status_code=503, detail=str(exc))

        # Step 4: AI Re-ranking
        candidates_str = self._compact_candidates(enriched[:12])
        intent_compact = (
            f"query:{req.preference[:120]} "
            f"genres:{intent_data.get('genres',[])} "
            f"moods:{intent_data.get('moods',[])} "
            f"actor:{intent_data.get('hero_actor','')}"
        )

        try:
            raw_rank, llm_used2 = await llm_manager.invoke(
                lambda llm: RERANK_PROMPT | llm | StrOutputParser(),
                {"intent": intent_compact[:200], "candidates": candidates_str[:1200], "count": req.count}
            )
            llm_used = llm_used2
            ranked = self._parse_json(raw_rank, [])
        except Exception as exc:
            logger.warning(f"Rerank failed: {exc}")
            ranked = [{"title": e["title"], "confidence": 0.80, "ai_reason": "", "why_matches": [], "mood_tags": []} for e in enriched]

        # Step 5: Build final cards
        by_title = {e["title"].lower(): e for e in enriched}

        def find_meta(title: str) -> Optional[dict]:
            tl = title.lower()
            if tl in by_title:
                return by_title[tl]
            tokens = {t for t in re.split(r"\W+", tl) if len(t) > 2}
            best, best_score = None, 0.0
            for k, v in by_title.items():
                kt = {t for t in re.split(r"\W+", k) if len(t) > 2}
                if tokens and kt:
                    overlap = len(tokens & kt) / max(len(tokens), len(kt))
                    if overlap > best_score:
                        best, best_score = v, overlap
            return best if best_score >= 0.72 else None

        final: list[MovieCard] = []
        used_iids: set[str] = set()
        for i, rm in enumerate(ranked[:req.count], 1):
            meta = find_meta(rm.get("title", ""))
            if not meta:
                continue
            iid = meta.get("imdb_id") or ""
            if iid and iid in used_iids:
                continue
            if iid:
                used_iids.add(iid)
            critics_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in meta.get("critics_reviews", [])]
            audience_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in meta.get("audience_reviews", [])]
            final.append(MovieCard(
                rank=i,
                title=meta["title"],
                content_type=meta.get("content_type", "movie"),
                year=meta.get("year"),
                end_year=meta.get("end_year"),
                overview=meta.get("overview"),
                genres=meta.get("genres", []),
                director=meta.get("director"),
                creator=meta.get("creator"),
                cast=meta.get("cast", []),
                runtime=meta.get("runtime"),
                seasons=meta.get("seasons"),
                language=meta.get("language"),
                country=meta.get("country"),
                awards=meta.get("awards"),
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
                critics_reviews=critics_r,
                audience_reviews=audience_r,
                watch_platforms_in=meta.get("platforms_in", []),
                watch_provider_links=meta.get("provider_links_in", []),
                combined_score=meta.get("combined_score"),
                llm_source=llm_used,
            ))

        # Fill gaps from top enriched
        if len(final) < req.count:
            for e in enriched:
                iid = e.get("imdb_id") or ""
                if iid and iid in used_iids:
                    continue
                used_iids.add(iid)
                critics_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in e.get("critics_reviews", [])]
                audience_r = [ReviewItem(**r) if isinstance(r, dict) else r for r in e.get("audience_reviews", [])]
                final.append(MovieCard(
                    rank=len(final) + 1,
                    title=e["title"],
                    content_type=e.get("content_type", "movie"),
                    year=e.get("year"),
                    end_year=e.get("end_year"),
                    overview=e.get("overview"),
                    genres=e.get("genres", []),
                    director=e.get("director"),
                    cast=e.get("cast", []),
                    runtime=e.get("runtime"),
                    seasons=e.get("seasons"),
                    language=e.get("language"),
                    ratings=MovieRatings(
                        imdb=e.get("imdb_rating"),
                        imdb_votes=e.get("imdb_votes"),
                        rotten_tomatoes=e.get("rt"),
                        metacritic=e.get("metacritic"),
                    ),
                    poster_url=e.get("poster"),
                    imdb_id=iid or None,
                    imdb_url=f"https://www.imdb.com/title/{iid}/" if iid else None,
                    confidence=0.78,
                    ai_reason="Selected by score ranking.",
                    critics_reviews=critics_r,
                    audience_reviews=audience_r,
                    watch_platforms_in=e.get("platforms_in", []),
                    watch_provider_links=e.get("provider_links_in", []),
                    combined_score=e.get("combined_score"),
                    llm_source=llm_used,
                ))
                if len(final) >= req.count:
                    break

        return RecommendationResponse(
            status="success",
            query_analysis=summary,
            recommendations=final,
            total_results=len(final),
            execution_time_ms=round((time.time() - t0) * 1000, 1),
            sources_used=list(dict.fromkeys(sources_used)),
            llm_used=llm_used,
            search_mode="recommend",
        )

    async def _handle_mood_timeline(self, req: RecommendationRequest) -> RecommendationResponse:
        """
        Build a 'light to intense' timeline for evening/weekend flow.
        """
        base_req = RecommendationRequest(**{
            "preference": req.preference,
            "watched": req.watched,
            "count": max(req.count, 6),
            "genres": req.genres,
            "hero_actor": req.hero_actor,
            "character_ref": req.character_ref,
            "content_types": req.content_types,
            "search_mode": "recommend",
            "language": req.language,
            "year_from": req.year_from,
            "year_to": req.year_to,
            "min_imdb": req.min_imdb,
            "min_rotten_tomatoes": req.min_rotten_tomatoes,
            "min_metacritic": req.min_metacritic,
        })
        rec = await self.recommend(base_req)

        def intensity(card: MovieCard) -> int:
            text = " ".join([
                card.title or "",
                card.overview or "",
                " ".join(card.genres or []),
                " ".join(card.mood_tags or []),
            ]).lower()
            score = 0
            low = ("family", "feel-good", "comedy", "romance", "animated")
            high = ("war", "horror", "thriller", "violent", "crime", "dark", "action")
            for t in low:
                if t in text:
                    score -= 1
            for t in high:
                if t in text:
                    score += 2
            return score

        rec.recommendations = sorted(rec.recommendations, key=intensity)
        for i, card in enumerate(rec.recommendations, 1):
            card.rank = i
            card.ai_reason = (card.ai_reason or "") + (" Timeline position: lighter start." if i <= 2 else " Timeline position: more intense.")
        rec.query_analysis = f"Mood timeline (light → intense) for: {req.preference}"
        rec.search_mode = "timeline"
        return rec


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI APP
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(title="CineAI v6", version="6.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_engine: Optional[CineAIEngine] = None

def get_engine() -> CineAIEngine:
    global _engine
    if _engine is None:
        _engine = CineAIEngine()
    return _engine


_WATCHLIST_FILE = Path(settings.data_dir) / "watchlist.json"


def _read_watchlist() -> list[dict]:
    if not _WATCHLIST_FILE.exists():
        return []
    try:
        return json.loads(_WATCHLIST_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_watchlist(items: list[dict]) -> None:
    _WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    _WATCHLIST_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/health", response_model=HealthResponse)
async def health(request: Request):
    _enforce_rate_limits(request)
    ollama_ok = await llm_manager.check_ollama()
    return HealthResponse(
        status="healthy",
        version="6.0.0",
        groq_configured=bool(settings.groq_api_key),
        omdb_configured=bool(settings.omdb_api_key),
        tmdb_configured=bool(settings.tmdb_api_key),
        ollama_available=ollama_ok,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/api/trending", response_model=TrendingResponse)
async def trending(request: Request):
    _enforce_rate_limits(request)
    # Daily refresh: update once per UTC day.
    cache_key = f"trending:{datetime.utcnow().strftime('%Y-%m-%d')}"
    engine = get_engine()
    cached = engine.cache.get(cache_key)
    if cached:
        return TrendingResponse(**cached, updated_at=datetime.utcnow().isoformat() + "Z")
    data = await get_engine().media.get_trending()
    engine.cache.set(cache_key, data)
    return TrendingResponse(**data, updated_at=datetime.utcnow().isoformat() + "Z")


@app.post("/api/compare")
async def compare_movies(payload: CompareRequest, request: Request):
    _enforce_rate_limits(request)
    engine = get_engine()
    d1, d2 = await asyncio.gather(
        engine.media.enrich(payload.title_1),
        engine.media.enrich(payload.title_2),
    )
    if not d1 or not d2:
        raise HTTPException(status_code=404, detail="Unable to resolve one or both movie titles for comparison.")
    return {
        "status": "success",
        "compare": [d1, d2],
        "summary": f"Comparison: {d1.get('title')} vs {d2.get('title')}",
    }


@app.get("/api/watchlist", response_model=WatchlistResponse)
async def get_watchlist(request: Request):
    _enforce_rate_limits(request)
    items = _read_watchlist()
    return WatchlistResponse(items=[WatchlistItem(**i) for i in items], alerts=[])


@app.post("/api/watchlist/add", response_model=WatchlistResponse)
async def add_watchlist(payload: WatchlistAddRequest, request: Request):
    _enforce_rate_limits(request)
    engine = get_engine()
    data = await engine.media.enrich(payload.title)
    if not data:
        raise HTTPException(status_code=404, detail="Title not found.")
    items = _read_watchlist()
    iid = data.get("imdb_id") or payload.title.lower()
    if any((x.get("imdb_id") or x.get("title", "").lower()) == iid for x in items):
        return WatchlistResponse(items=[WatchlistItem(**i) for i in items], alerts=["Already in watchlist."])
    items.append({
        "title": data.get("title", payload.title),
        "imdb_id": data.get("imdb_id"),
        "poster_url": data.get("poster"),
        "watch_platforms_in": data.get("platforms_in", []),
        "new_platforms_in": [],
        "last_checked_at": datetime.utcnow().isoformat() + "Z",
    })
    _write_watchlist(items)
    return WatchlistResponse(items=[WatchlistItem(**i) for i in items], alerts=["Added to watchlist."])


@app.post("/api/watchlist/remove")
async def remove_watchlist(payload: WatchlistAddRequest, request: Request):
    _enforce_rate_limits(request)
    items = _read_watchlist()
    before = len(items)
    q = payload.title.strip().lower()
    items = [i for i in items if i.get("title", "").strip().lower() != q]
    _write_watchlist(items)
    return {"status": "success", "removed": before - len(items)}


@app.post("/api/watchlist/check", response_model=WatchlistResponse)
async def check_watchlist_changes(request: Request):
    _enforce_rate_limits(request)
    engine = get_engine()
    items = _read_watchlist()
    alerts: list[str] = []
    updated: list[dict] = []
    for item in items:
        title = item.get("title", "")
        fresh = await engine.media.enrich(title)
        if not fresh:
            updated.append(item)
            continue
        old_set = set(item.get("watch_platforms_in", []))
        new_set = set(fresh.get("platforms_in", []))
        newly_added = sorted(list(new_set - old_set))
        if newly_added:
            alerts.append(f"{title}: New in India - {', '.join(newly_added[:3])}")
        updated.append({
            "title": fresh.get("title", title),
            "imdb_id": fresh.get("imdb_id"),
            "poster_url": fresh.get("poster"),
            "watch_platforms_in": list(new_set),
            "new_platforms_in": newly_added,
            "last_checked_at": datetime.utcnow().isoformat() + "Z",
        })
    _write_watchlist(updated)
    return WatchlistResponse(items=[WatchlistItem(**i) for i in updated], alerts=alerts)


@app.post("/api/recommend", response_model=RecommendationResponse)
async def recommend(req: RecommendationRequest, request: Request):
    _enforce_rate_limits(request)
    try:
        response = await get_engine().recommend(req)
        # Sanitize all text outputs
        for card in response.recommendations:
            card.title = _safe_text(card.title, 140) or ""
            card.overview = _safe_text(card.overview, 500)
            card.director = _safe_text(card.director, 120)
            card.creator = _safe_text(card.creator, 120)
            card.cast = _safe_list(card.cast, max_items=6, item_limit=80)
            card.genres = _safe_list(card.genres, max_items=8, item_limit=40)
            card.ai_reason = _safe_text(card.ai_reason, 400) or ""
            card.why_matches = _safe_list(card.why_matches, max_items=5, item_limit=120)
            card.mood_tags = _safe_list(card.mood_tags, max_items=6, item_limit=40)
            card.similar_to = _safe_text(card.similar_to, 200)
            card.similar_titles = _safe_list(card.similar_titles, max_items=8, item_limit=80)
            card.best_review = _safe_text(card.best_review, 400)
            card.actor_bio = _safe_text(card.actor_bio, 400)
            card.awards = _safe_text(card.awards, 200)
            card.watch_platforms_in = _safe_list(card.watch_platforms_in, max_items=8, item_limit=40)
            safe_links = []
            for link in (card.watch_provider_links or [])[:8]:
                if not isinstance(link, dict):
                    continue
                name = _safe_text(link.get("name"), 40) or ""
                url = str(link.get("url") or "").strip()
                if not name:
                    continue
                if url.startswith("http://") or url.startswith("https://"):
                    safe_links.append({"name": name, "url": url})
                else:
                    safe_links.append({"name": name, "url": ""})
            card.watch_provider_links = safe_links
            # Sanitize reviews
            for rv in card.critics_reviews + card.audience_reviews:
                rv.author = _safe_text(rv.author, 80)
                rv.content = _safe_text(rv.content, 350)
        response.query_analysis = _safe_text(response.query_analysis, 400) or ""
        return response
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Recommendation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/llm-status")
async def llm_status(request: Request):
    _enforce_rate_limits(request)
    ollama_ok = await llm_manager.check_ollama()
    return {
        "groq_configured": bool(settings.groq_api_key),
        "groq_in_backoff": llm_manager.groq_in_backoff(),
        "ollama_available": ollama_ok,
        "ollama_model": settings.ollama_model,
        "active_llm": f"ollama/{settings.ollama_model}" if llm_manager.groq_in_backoff() else "groq/llama-3.1-8b-instant",
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    _enforce_rate_limits(request)
    return HTMLResponse(content=_UI_HTML)


# ═══════════════════════════════════════════════════════════════════════════
# UI — CINEMATIC DARK THEME v6
# ═══════════════════════════════════════════════════════════════════════════

_UI_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>CineAI v6 — Smart Movie Recommendations</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet"/>
<style>
:root {
  --bg: #05080f;
  --surface: #0a0e1a;
  --surface2: #101525;
  --surface3: #161d2e;
  --border: #1c2640;
  --border2: #263050;
  --accent: #e8952a;
  --accent2: #ff6b35;
  --gold: #f5c518;
  --rt-red: #fa4609;
  --mc-green: #66cc7a;
  --teal: #1de9b6;
  --purple: #8b7cf8;
  --blue: #4fc3f7;
  --text: #dce8f5;
  --muted: #6a84a0;
  --muted2: #3a4f65;
  --r: 14px;
  --display: 'Bebas Neue', sans-serif;
  --serif: 'DM Serif Display', serif;
  --body: 'DM Sans', sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--body);
  font-weight: 300;
  min-height: 100vh;
  overflow-x: hidden;
}

/* Film grain texture */
body::before {
  content: '';
  position: fixed; inset: 0; pointer-events: none; z-index: 999;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
  opacity: 0.35;
}

/* ── HEADER ── */
header {
  position: relative;
  padding: 3rem 2rem 2rem;
  text-align: center;
  background:
    radial-gradient(ellipse 80% 60% at 50% -10%, rgba(232,149,42,.18), transparent 60%),
    radial-gradient(ellipse 40% 30% at 85% 70%, rgba(139,124,248,.1), transparent 55%);
  border-bottom: 1px solid rgba(255,255,255,.06);
  overflow: hidden;
}
header::after {
  content: '';
  position: absolute; bottom: 0; left: 10%; right: 10%; height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent), var(--accent2), transparent);
  opacity: 0.6;
}

.logo-wrap { display: flex; align-items: baseline; justify-content: center; gap: .4rem; }
.logo {
  font-family: var(--display);
  font-size: clamp(4rem, 12vw, 9rem);
  letter-spacing: .04em;
  line-height: 1;
  background: linear-gradient(135deg, #fff 0%, var(--accent) 35%, #fff 55%, var(--accent2) 80%, #fff 100%);
  background-size: 300%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shimmer 5s linear infinite;
}
@keyframes shimmer { 0% { background-position: 0% } 100% { background-position: 300% } }
.logo-v { font-family: var(--display); font-size: clamp(1.5rem, 4vw, 3rem); -webkit-text-fill-color: var(--accent); opacity: .7; }
.tagline {
  margin-top: .5rem;
  font-size: .68rem;
  letter-spacing: .3em;
  text-transform: uppercase;
  color: var(--muted);
}
.tagline b { color: var(--accent); font-weight: 500; }

/* LLM bar */
#llm-bar {
  max-width: 680px;
  margin: .8rem auto 0;
  display: flex; align-items: center; justify-content: center; gap: .5rem; flex-wrap: wrap;
}
.llm-chip {
  font-size: .62rem; letter-spacing: .07em; text-transform: uppercase;
  padding: .18rem .55rem; border-radius: 20px; border: 1px solid;
  display: flex; align-items: center; gap: .28rem;
}
.chip-groq { border-color: #6b5aed; color: #9b8ff5; background: rgba(107,90,237,.1); }
.chip-ollama { border-color: var(--mc-green); color: var(--mc-green); background: rgba(102,204,122,.08); }
.chip-warn { border-color: var(--accent); color: var(--accent); background: rgba(232,149,42,.1); }
.dot { width: 5px; height: 5px; border-radius: 50%; animation: blink 1.6s ease infinite; }
.dot-p { background: #9b8ff5; }
.dot-g { background: var(--mc-green); }
.dot-o { background: var(--accent); }
@keyframes blink { 0%,100% { opacity:1 } 50% { opacity:.25 } }

/* ── MAIN LAYOUT ── */
.main-wrap { max-width: 900px; margin: 0 auto; padding: 2rem 1.5rem; }

/* Search panel */
.search-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 2rem 2.2rem;
  position: relative; overflow: hidden;
}
.search-panel::before {
  content: '';
  position: absolute; top: -80px; right: -80px; width: 240px; height: 240px;
  background: radial-gradient(circle, rgba(232,149,42,.07), transparent 70%);
  pointer-events: none;
}

/* Mode tabs */
.mode-tabs {
  display: flex; gap: .35rem; margin-bottom: 1.5rem; flex-wrap: wrap;
}
.mode-tab {
  padding: .42rem 1.1rem; border-radius: 8px; border: 1px solid var(--border2);
  background: transparent; color: var(--muted); font-size: .72rem; letter-spacing: .08em;
  text-transform: uppercase; cursor: pointer; transition: all .18s; font-family: var(--body);
  display: flex; align-items: center; gap: .4rem;
}
.mode-tab.active {
  background: rgba(232,149,42,.12); border-color: var(--accent); color: var(--accent);
}
.mode-tab:hover:not(.active) { border-color: var(--muted2); color: var(--text); }

/* Input fields */
label {
  display: block; font-size: .62rem; letter-spacing: .18em; text-transform: uppercase;
  color: var(--muted); margin-bottom: .38rem; font-weight: 500;
}
textarea, input, select {
  width: 100%;
  background: rgba(0,0,0,.5);
  border: 1px solid var(--border);
  border-radius: 9px;
  color: var(--text);
  font-family: var(--body); font-size: .88rem; font-weight: 300;
  padding: .75rem 1rem;
  outline: none;
  transition: border-color .2s, box-shadow .2s;
}
textarea { min-height: 82px; resize: vertical; line-height: 1.55; }
textarea:focus, input:focus, select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(232,149,42,.1); }
::placeholder { color: var(--muted2); }
select { height: 42px; cursor: pointer; }
select option { background: var(--surface2); }

.g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.g3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }
.field { margin-top: 1rem; }
@media(max-width: 580px) { .g2, .g3 { grid-template-columns: 1fr; } }

/* Type toggles */
.type-row { display: flex; gap: .35rem; flex-wrap: wrap; }
.type-btn {
  padding: .35rem .85rem; border-radius: 20px; border: 1px solid var(--border2);
  background: transparent; color: var(--muted); font-size: .68rem; letter-spacing: .07em;
  text-transform: uppercase; cursor: pointer; transition: all .18s; font-family: var(--body);
}
.type-btn.active { background: rgba(232,149,42,.12); border-color: var(--accent); color: var(--accent); }

hr.sep { border: none; border-top: 1px solid var(--border); margin: 1.4rem 0; }

/* Advanced section */
.adv-toggle {
  width: 100%;
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(255,255,255,.02); border: 1px solid var(--border);
  color: var(--muted); border-radius: 9px; padding: .65rem 1rem;
  cursor: pointer; font-size: .68rem; letter-spacing: .12em; text-transform: uppercase;
  transition: all .2s; font-family: var(--body);
}
.adv-toggle:hover { border-color: var(--border2); color: var(--text); }
.adv-toggle.open { border-color: var(--accent); color: var(--accent); }
.adv-toggle .arr { transition: transform .2s; }
.adv-toggle.open .arr { transform: rotate(180deg); }
.adv-wrap { display: none; margin-top: 1rem; animation: rise .2s ease both; }
.adv-wrap.open { display: block; }

.sec-lbl {
  font-size: .58rem; letter-spacing: .2em; text-transform: uppercase;
  color: var(--muted2); display: flex; align-items: center; gap: .5rem; margin-bottom: .9rem;
}
.sec-lbl::after { content: ''; flex: 1; height: 1px; background: var(--border); }

/* CTA Button */
.cta-btn {
  width: 100%; margin-top: 1.6rem; padding: .95rem; border: none; border-radius: 10px;
  cursor: pointer; font-family: var(--display);
  font-size: 1.6rem; letter-spacing: .1em;
  background: linear-gradient(135deg, #f5a623 0%, #e07510 50%, #f5a623 100%);
  background-size: 200%; color: #000;
  transition: background-position .4s, transform .15s, box-shadow .2s;
  box-shadow: 0 4px 28px rgba(232,149,42,.35);
}
.cta-btn:hover:not(:disabled) { background-position: right; transform: translateY(-2px); box-shadow: 0 8px 36px rgba(232,149,42,.5); }
.cta-btn:disabled { opacity: .35; cursor: not-allowed; }

/* ── TRENDING ── */
#trending-section { max-width: 1400px; margin: 2.5rem auto; padding: 0 1.5rem; }
.section-hdr {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.2rem;
}
.section-hdr h2 { font-family: var(--display); font-size: 1.6rem; letter-spacing: .05em; }
.section-hdr span { font-size: .65rem; color: var(--muted); letter-spacing: .1em; text-transform: uppercase; }
.trending-row { display: flex; gap: .9rem; overflow-x: auto; padding-bottom: .6rem; scroll-snap-type: x mandatory; }
.trending-row::-webkit-scrollbar { height: 3px; }
.trending-row::-webkit-scrollbar-track { background: var(--surface2); border-radius: 2px; }
.trending-row::-webkit-scrollbar-thumb { background: var(--accent); border-radius: 2px; }
.t-card {
  flex: 0 0 140px; scroll-snap-align: start;
  border-radius: 10px; overflow: hidden; position: relative;
  cursor: pointer; transition: transform .25s, box-shadow .25s;
  border: 1px solid var(--border);
}
.t-card:hover { transform: scale(1.05); box-shadow: 0 10px 30px rgba(0,0,0,.7); }
.t-card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }
.t-card-overlay {
  position: absolute; bottom: 0; left: 0; right: 0;
  background: linear-gradient(transparent, rgba(0,0,0,.9));
  padding: .8rem .5rem .4rem;
}
.t-card-title { font-size: .7rem; font-weight: 500; line-height: 1.2; }
.t-card-rating { font-size: .62rem; color: var(--gold); margin-top: .15rem; }
.t-badge {
  position: absolute; top: .4rem; right: .4rem; z-index: 2;
  font-size: .55rem; letter-spacing: .06em; text-transform: uppercase;
  padding: .12rem .35rem; border-radius: 4px;
}
.tb-new { background: rgba(29,233,182,.2); border: 1px solid var(--teal); color: var(--teal); }

/* ── LOADER ── */
#loader { display: none; text-align: center; padding: 5rem 2rem; }
.film-strip {
  display: flex; justify-content: center; gap: .5rem; margin-bottom: 1.5rem;
}
.film-cell {
  width: 40px; height: 56px; border-radius: 4px;
  background: var(--surface2); border: 2px solid var(--border);
  animation: filmroll .6s ease infinite;
}
.film-cell:nth-child(1) { animation-delay: 0s; }
.film-cell:nth-child(2) { animation-delay: .1s; }
.film-cell:nth-child(3) { animation-delay: .2s; }
.film-cell:nth-child(4) { animation-delay: .3s; }
.film-cell:nth-child(5) { animation-delay: .4s; }
@keyframes filmroll {
  0%, 100% { background: var(--surface2); border-color: var(--border); }
  50% { background: var(--surface3); border-color: var(--accent); }
}
.load-txt { font-size: .7rem; letter-spacing: .25em; text-transform: uppercase; color: var(--muted); }

/* ── STATUS BAR ── */
#status-bar { max-width: 1400px; margin: 0 auto 1.8rem; padding: 0 1.5rem; display: none; }
.analysis-box {
  background: var(--surface); border: 1px solid var(--border); border-radius: var(--r);
  padding: .9rem 1.4rem; display: flex; align-items: center; gap: .9rem; flex-wrap: wrap;
}
.analysis-box p { font-size: .82rem; color: var(--muted); flex: 1; line-height: 1.5; }
.analysis-box strong { color: var(--text); }
.exec-time { font-size: .68rem; color: var(--muted2); white-space: nowrap; }
.src-chips { display: flex; gap: .3rem; flex-wrap: wrap; }
.src-chip {
  font-size: .6rem; letter-spacing: .07em; text-transform: uppercase;
  padding: .15rem .5rem; border-radius: 20px; border: 1px solid;
}
.sc-llm { border-color: #6b5aed; color: #9b8ff5; }
.sc-omdb { border-color: var(--gold); color: var(--gold); }
.sc-tmdb { border-color: var(--teal); color: var(--teal); }

/* ── RESULTS GRID ── */
#results { max-width: 1400px; margin: 0 auto; padding: 0 1.5rem 5rem; }
.results-hdr { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.6rem; }
.results-hdr h2 { font-family: var(--display); font-size: 2rem; letter-spacing: .04em; }
.results-hdr span { font-size: .68rem; color: var(--muted); letter-spacing: .1em; text-transform: uppercase; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 1.5rem; align-items: start; }
@media(max-width: 850px) { .grid { grid-template-columns: 1fr; } }

/* ── MOVIE CARD ── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  overflow: hidden;
  display: flex; flex-direction: column;
  transition: transform .3s ease, box-shadow .3s, border-color .3s;
  animation: rise .45s ease both;
  position: relative;
}
.card:hover { transform: translateY(-6px); box-shadow: 0 24px 60px rgba(0,0,0,.75); border-color: var(--border2); }
@keyframes rise { from { opacity: 0; transform: translateY(28px); } to { opacity: 1; transform: none; } }

/* POSTER */
.poster-wrap { position: relative; flex-shrink: 0; }
.poster-img-area {
  aspect-ratio: 2/3;
  overflow: hidden;
  background: #070b14;
  position: relative;
  min-height: 360px;
  cursor: pointer;
}
.poster-img-area img {
  width: 100%; height: 100%; object-fit: contain;
  transition: transform .4s ease;
}
.card:hover .poster-img-area img { transform: scale(1.04); }

/* Fallback poster */
.poster-fallback {
  width: 100%; height: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: .7rem; text-align: center; padding: 1.5rem;
  position: relative;
}
.pf-icon { font-size: 3rem; position: relative; z-index: 1; filter: drop-shadow(0 4px 12px rgba(0,0,0,.6)); }
.pf-title { font-family: var(--serif); font-size: 1.2rem; color: rgba(255,255,255,.9); position: relative; z-index: 1; line-height: 1.2; }
.pf-year { font-size: .7rem; color: rgba(255,255,255,.4); position: relative; z-index: 1; }

/* Poster overlays */
.poster-overlays { position: absolute; inset: 0; pointer-events: none; z-index: 3; }
.ov-rank {
  position: absolute; top: .7rem; left: .7rem;
  background: var(--accent); color: #000;
  font-family: var(--display); font-size: 1.4rem;
  padding: .05rem .5rem; border-radius: 6px; line-height: 1.3;
}
.ov-match {
  position: absolute; top: .7rem; right: .7rem;
  background: rgba(0,0,0,.75); backdrop-filter: blur(8px);
  border: 1px solid rgba(255,255,255,.12); border-radius: 20px;
  font-size: .62rem; padding: .15rem .5rem; color: #fff;
}
.ov-ct {
  position: absolute; bottom: .7rem; left: .7rem;
  font-size: .58rem; letter-spacing: .1em; text-transform: uppercase;
  padding: .18rem .5rem; border-radius: 5px;
}
.ct-movie { background: rgba(232,149,42,.2); border: 1px solid rgba(232,149,42,.5); color: var(--accent); }
.ct-series { background: rgba(29,233,182,.15); border: 1px solid rgba(29,233,182,.45); color: var(--teal); }
.ct-short { background: rgba(102,204,122,.15); border: 1px solid rgba(102,204,122,.5); color: var(--mc-green); }
.ov-score {
  position: absolute; bottom: .7rem; right: .7rem;
  border-radius: 8px; padding: .25rem .5rem; font-size: .7rem; font-weight: 600;
  backdrop-filter: blur(8px);
}
.score-hi { background: rgba(102,204,122,.25); border: 1px solid rgba(102,204,122,.6); color: var(--mc-green); }
.score-md { background: rgba(245,197,24,.22); border: 1px solid rgba(245,197,24,.5); color: var(--gold); }
.score-lo { background: rgba(250,70,9,.18); border: 1px solid rgba(250,70,9,.5); color: var(--rt-red); }
.ov-llm {
  position: absolute; top: 2.6rem; right: .7rem;
  font-size: .54rem; letter-spacing: .06em; padding: .1rem .38rem; border-radius: 20px;
  background: rgba(139,124,248,.22); border: 1px solid rgba(139,124,248,.5); color: #c4bbff;
}

/* CARD BODY */
.cbody { padding: 1.1rem 1.2rem 1.3rem; flex: 1; display: flex; flex-direction: column; gap: .7rem; }

.c-title-row { display: flex; align-items: flex-start; gap: .5rem; }
.c-title { font-family: var(--serif); font-size: 1.3rem; font-weight: 400; line-height: 1.15; flex: 1; }
.c-year { font-size: .78rem; color: var(--muted); white-space: nowrap; padding-top: .15rem; }

.c-meta { font-size: .72rem; color: var(--muted); display: flex; flex-wrap: wrap; gap: .2rem .5rem; align-items: center; }
.c-dot { color: var(--muted2); }
.person-link {
  cursor: pointer; color: #9fd8ff; border-bottom: 1px dashed rgba(159,216,255,.35);
}
.person-link:hover { color: #c9ecff; border-bottom-color: #c9ecff; }
.person-link[title] { position: relative; }
.sim-links { display:flex; flex-wrap:wrap; gap:.3rem; }
.sim-chip {
  cursor:pointer; font-size:.62rem; padding:.16rem .42rem; border-radius:14px;
  background: rgba(139,124,248,.12); border:1px solid rgba(139,124,248,.35); color: var(--purple);
}
.sim-chip:hover { background: rgba(139,124,248,.24); }

/* Genres */
.c-genres { display: flex; flex-wrap: wrap; gap: .3rem; }
.genre-tag {
  font-size: .6rem; letter-spacing: .06em; text-transform: uppercase;
  padding: .14rem .42rem; border-radius: 4px;
  background: rgba(232,149,42,.08); border: 1px solid rgba(232,149,42,.2); color: var(--accent);
}

/* RATINGS ROW — prominent */
.ratings-row {
  display: flex; gap: 0; align-items: stretch;
  background: var(--surface2); border: 1px solid var(--border); border-radius: 10px;
  overflow: hidden;
}
.rating-block {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: .6rem .4rem; gap: .15rem;
  border-right: 1px solid var(--border);
  transition: background .18s;
}
.rating-block:last-child { border-right: none; }
.rating-block:hover { background: rgba(255,255,255,.03); }
.rb-ico { font-size: 1rem; }
.rb-val { font-size: 1rem; font-weight: 600; letter-spacing: -.01em; }
.rb-lbl { font-size: .55rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted2); }
.rv-imdb { color: var(--gold); }
.rv-rt { color: var(--rt-red); }
.rv-mc { color: var(--mc-green); }
.votes-lbl { font-size: .58rem; color: var(--muted2); }

/* Overview */
.c-overview {
  font-size: .78rem; color: var(--muted); line-height: 1.65;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}

/* Watch in India */
.platforms-row {
  background: rgba(29,233,182,.05); border: 1px solid rgba(29,233,182,.18);
  border-radius: 8px; padding: .55rem .8rem;
  display: flex; align-items: flex-start; gap: .55rem; flex-wrap: wrap;
}
.platforms-lbl { font-size: .6rem; letter-spacing: .1em; text-transform: uppercase; color: var(--teal); flex-shrink: 0; padding-top: .1rem; }
.platforms-list { font-size: .73rem; color: var(--text); flex: 1; }
.platforms-empty { font-size: .73rem; color: var(--muted2); font-style: italic; }
.provider-links { display: flex; gap: .35rem; flex-wrap: wrap; flex: 1; }
.provider-link {
  display: inline-flex; align-items: center; gap: .32rem;
  font-size: .62rem; letter-spacing: .04em; text-decoration: none;
  color: var(--teal); border: 1px solid rgba(29,233,182,.35);
  padding: .18rem .42rem; border-radius: 14px; background: rgba(29,233,182,.08);
}
.provider-link:hover { background: rgba(29,233,182,.15); border-color: var(--teal); }
.provider-logo {
  width: 14px; height: 14px; border-radius: 3px; object-fit: contain; background: rgba(255,255,255,.06);
}
.provider-emoji { font-size: .74rem; line-height: 1; }

/* Compact ratings strip requested by UX */
.mini-ratings {
  display: flex; gap: .4rem; flex-wrap: wrap;
}
.mini-chip {
  display: inline-flex; align-items: center; gap: .35rem;
  font-size: .66rem; padding: .16rem .45rem; border-radius: 16px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.03); color: var(--text);
}
.mini-chip .icon { font-size: .78rem; line-height: 1; }
.mini-chip .label { color: var(--muted2); letter-spacing: .05em; text-transform: uppercase; font-size: .54rem; }
.mini-chip.imdb { border-color: rgba(245,197,24,.35); }
.mini-chip.rt { border-color: rgba(250,70,9,.35); }

/* AI Reason */
.ai-block {
  background: var(--surface2); border: 1px solid var(--border2);
  border-radius: 9px; padding: .85rem;
}
.ai-reason { font-size: .78rem; font-style: italic; color: #9ab8d4; line-height: 1.65; }
.why-list { list-style: none; margin-top: .5rem; display: flex; flex-direction: column; gap: .28rem; }
.why-list li { font-size: .72rem; color: var(--muted); display: flex; gap: .4rem; align-items: flex-start; }
.why-list li::before { content: '◆'; color: var(--accent); flex-shrink: 0; font-size: .5rem; margin-top: .2rem; }
.c-similar { font-size: .7rem; color: var(--teal); margin-top: .4rem; font-style: italic; }

/* REVIEWS */
.reviews-section { display: flex; flex-direction: column; gap: .5rem; }
.tap-hint {
  font-size: .6rem; color: var(--muted2); letter-spacing: .08em;
  text-transform: uppercase; margin-top: -.1rem;
}
.details-panel { display: none; }
.details-panel.open { display: block; animation: rise .2s ease both; }
.review-hdr { font-size: .6rem; letter-spacing: .14em; text-transform: uppercase; color: var(--muted2); display: flex; align-items: center; gap: .4rem; }
.review-hdr::after { content: ''; flex: 1; height: 1px; background: var(--border); }
.review-item {
  background: rgba(255,255,255,.025); border-radius: 8px; padding: .65rem .8rem;
  border-left: 3px solid;
}
.review-critic { border-left-color: var(--gold); }
.review-audience { border-left-color: var(--purple); }
.rv-author { font-size: .65rem; color: var(--muted2); margin-bottom: .25rem; display: flex; align-items: center; gap: .4rem; }
.rv-rating-badge { font-size: .58rem; padding: .08rem .3rem; border-radius: 3px; background: rgba(245,197,24,.15); color: var(--gold); }
.rv-text { font-size: .75rem; color: var(--muted); line-height: 1.6; font-style: italic; }
.rv-text::before { content: '"'; color: var(--gold); }
.rv-text::after { content: '"'; color: var(--gold); }

/* Actor bio */
.actor-bio-block {
  background: rgba(79,195,247,.05); border: 1px solid rgba(79,195,247,.2);
  border-radius: 9px; padding: .85rem;
}
.actor-bio-text { font-size: .78rem; color: #aac8e0; line-height: 1.65; }
.known-for-list { font-size: .72rem; color: var(--muted); margin-top: .4rem; }

/* Character name */
.char-badge {
  display: inline-flex; align-items: center; gap: .35rem;
  font-size: .68rem; padding: .22rem .65rem; border-radius: 20px;
  background: rgba(139,124,248,.12); border: 1px solid rgba(139,124,248,.35); color: var(--purple);
}

/* Awards */
.awards-row {
  font-size: .7rem; color: var(--gold);
  display: flex; align-items: flex-start; gap: .4rem; opacity: .8;
}

/* Mood tags */
.mood-tags { display: flex; flex-wrap: wrap; gap: .28rem; }
.mood-tag {
  font-size: .6rem; padding: .14rem .42rem; border-radius: 20px;
  background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); color: var(--muted);
}
.new-ott-row { display:flex; flex-wrap:wrap; gap:.28rem; }
.new-ott-badge {
  font-size:.58rem; padding:.14rem .4rem; border-radius:14px;
  background: rgba(102,204,122,.18); border:1px solid rgba(102,204,122,.45); color: var(--mc-green);
  letter-spacing:.04em; text-transform: uppercase;
}

/* IMDb link */
.imdb-link {
  display: block; text-align: center; padding: .45rem; border-radius: 7px;
  margin-top: auto; font-size: .68rem; letter-spacing: .05em; text-decoration: none;
  border: 1px solid rgba(245,197,24,.25); color: var(--gold);
  transition: all .2s;
}
.imdb-link:hover { background: rgba(245,197,24,.1); border-color: var(--gold); }

/* Error */
.error-box {
  background: rgba(255,80,80,.08); border: 1px solid rgba(255,80,80,.3);
  border-radius: var(--r); padding: 1.5rem; color: #ff7070; max-width: 900px; margin: 2rem auto;
}
.help-fab {
  position: fixed; right: 20px; bottom: 20px; z-index: 1200;
  width: 40px; height: 40px; border-radius: 50%;
  border: 1px solid rgba(232,149,42,.5); background: rgba(10,16,28,.92);
  color: var(--accent); font-size: 1.05rem; cursor: pointer;
  box-shadow: 0 8px 24px rgba(0,0,0,.45);
}
.help-fab:hover { background: rgba(232,149,42,.16); }
.help-panel {
  position: fixed; right: 20px; bottom: 68px; z-index: 1200;
  width: 260px; padding: .8rem .85rem;
  border-radius: 12px; border: 1px solid var(--border2);
  background: rgba(10,16,28,.96); display: none;
}
.help-panel.open { display: block; }
.help-title { font-size: .62rem; letter-spacing: .12em; text-transform: uppercase; color: var(--muted2); margin-bottom: .5rem; }
.help-row { display: flex; justify-content: space-between; gap: .6rem; font-size: .68rem; color: var(--muted); padding: .12rem 0; }
.help-row b { color: var(--text); font-weight: 500; }
.breadcrumb-wrap {
  max-width:1400px; margin: .2rem auto .8rem; padding:0 1.5rem; display:none;
}
.breadcrumb {
  display:flex; flex-wrap:wrap; gap:.35rem; align-items:center;
}
.crumb {
  font-size:.62rem; letter-spacing:.06em; text-transform:uppercase;
  padding:.16rem .46rem; border-radius:14px; cursor:pointer;
  border:1px solid var(--border); color:var(--muted); background:rgba(255,255,255,.02);
}
.crumb.active { color:var(--text); border-color:var(--accent); background:rgba(232,149,42,.1); }
</style>
</head>
<body>

<!-- HEADER -->
<header>
  <div class="logo-wrap">
    <span class="logo">CineAI</span>
    <span class="logo-v">v6</span>
  </div>
  <p class="tagline">IMDb · <b>Rotten Tomatoes</b> · Metacritic · <b>Groq + Mistral</b> · Watch in India · AI-Powered</p>
  <div id="llm-bar"></div>
</header>

<!-- SEARCH PANEL -->
<div class="main-wrap">
  <div class="search-panel">

    <!-- Mode tabs -->
    <div class="mode-tabs" id="mode-tabs">
      <button class="mode-tab active" data-mode="recommend" onclick="setMode(this)">🧠 Recommend</button>
      <button class="mode-tab" data-mode="movie" onclick="setMode(this)">🎬 Movie Search</button>
      <button class="mode-tab" data-mode="actor" onclick="setMode(this)">⭐ Actor Search</button>
      <button class="mode-tab" data-mode="character" onclick="setMode(this)">🦸 Character Search</button>
      <button class="mode-tab" data-mode="timeline" onclick="setMode(this)">🕘 Mood Timeline</button>
      <button class="mode-tab" data-mode="compare" onclick="setMode(this)">⚖️ Compare 2 Movies</button>
    </div>

    <div class="field">
      <label id="main-label" for="pref">What are you in the mood for?</label>
      <textarea id="pref" rows="3" placeholder="e.g. A dark psychological thriller with an unreliable narrator — tense atmosphere, mind-bending twist, like Gone Girl or Shutter Island…"></textarea>
    </div>
    <div class="field" id="compare-field" style="display:none">
      <label for="pref2">Second movie name for comparison</label>
      <input id="pref2" placeholder="e.g. John Wick"/>
    </div>

    <hr class="sep"/>
    <button class="adv-toggle" id="adv-toggle" onclick="toggleAdv()" type="button">
      <span>Advanced Filters</span>
      <span class="arr">▼</span>
    </button>

    <div class="adv-wrap" id="adv-wrap">
      <div class="sec-lbl" style="margin-top:.9rem">Filters</div>
      <div class="g3">
        <div><label for="genres">Genres</label><input id="genres" placeholder="Action, Sci-Fi, Tamil…"/></div>
        <div><label for="hero">Actor / Director</label><input id="hero" placeholder="Vijay, Nolan, Tarantino…"/></div>
        <div><label for="charref">Franchise / Character</label><input id="charref" placeholder="Batman, Marvel, Thala…"/></div>
      </div>
      <div class="g2" style="margin-top:1rem">
        <div><label for="language">Language</label><input id="language" placeholder="Tamil, Hindi, English, Telugu…"/></div>
        <div><label for="watched">Already seen (skip)</label><input id="watched" placeholder="Inception, Vikram…"/></div>
      </div>
      <div class="g3" style="margin-top:1rem">
        <div><label for="yr-from">Year from</label><input id="yr-from" type="number" min="1900" max="2100" placeholder="2000"/></div>
        <div><label for="yr-to">Year to</label><input id="yr-to" type="number" min="1900" max="2100" placeholder="2025"/></div>
        <div><label for="min-imdb">Min IMDb</label><input id="min-imdb" type="number" min="0" max="10" step="0.1" placeholder="7.0"/></div>
      </div>
      <div class="g2" style="margin-top:1rem">
        <div><label for="min-rt">Min Rotten Tomatoes %</label><input id="min-rt" type="number" min="0" max="100" placeholder="70"/></div>
        <div><label for="min-mc">Min Metacritic</label><input id="min-mc" type="number" min="0" max="100" placeholder="60"/></div>
      </div>
      <div class="field">
        <label>Count</label>
        <input id="count" type="number" min="1" max="10" value="6" style="max-width:100px"/>
      </div>
      <div class="field">
        <label>Content Type</label>
        <div class="type-row" id="type-row">
          <button class="type-btn active" data-type="movie" onclick="toggleType(this)">🎬 Movies</button>
          <button class="type-btn" data-type="series" onclick="toggleType(this)">📺 Series</button>
          <button class="type-btn" data-type="short" onclick="toggleType(this)">🎞 Shorts</button>
        </div>
      </div>
    </div>

    <button class="cta-btn" id="cta" onclick="go()">FIND MY FILMS</button>
    <div class="type-row" style="margin-top:.7rem">
      <button class="type-btn" type="button" onclick="addCurrentToWatchlist()">➕ Add to Watchlist</button>
      <button class="type-btn" type="button" onclick="refreshWatchlistAlerts()">🔔 Check OTT Alerts</button>
      <button class="type-btn" type="button" onclick="loadWatchlist()">📚 View Watchlist</button>
    </div>
  </div>
</div>

<!-- TRENDING -->
<div id="trending-section" style="display:none">
  <div class="section-hdr">
    <h2>🔥 Trending This Week</h2>
    <span id="trending-updated"></span>
  </div>
  <p style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:.6rem">Movies</p>
  <div class="trending-row" id="trending-movies"></div>
  <p style="font-size:.7rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:.9rem 0 .6rem">Series</p>
  <div class="trending-row" id="trending-series"></div>
</div>

<!-- LOADER -->
<div id="loader">
  <div class="film-strip">
    <div class="film-cell"></div><div class="film-cell"></div>
    <div class="film-cell"></div><div class="film-cell"></div><div class="film-cell"></div>
  </div>
  <p class="load-txt">Querying IMDb · Rotten Tomatoes · Metacritic · TMDB…</p>
</div>

<!-- STATUS BAR -->
<div id="status-bar">
  <div class="analysis-box">
    <span style="font-size:1.2rem">🧠</span>
    <p><strong>AI understood: </strong><span id="ai-summary"></span></p>
    <div class="src-chips" id="src-chips"></div>
    <span class="exec-time" id="exec-t"></span>
  </div>
</div>

<div class="breadcrumb-wrap" id="breadcrumb-wrap">
  <div class="breadcrumb" id="breadcrumb"></div>
</div>

<!-- RESULTS -->
<div id="results">
  <div class="results-hdr" id="results-hdr" style="display:none">
    <h2 id="rh-title">Results</h2>
    <span id="rh-sub"></span>
  </div>
  <div class="grid" id="grid"></div>
</div>
<div id="watchlist-panel" style="max-width:1400px;margin:0 auto 2rem;padding:0 1.5rem;display:none">
  <div class="analysis-box">
    <span style="font-size:1.2rem">📚</span>
    <p><strong>Smart Watchlist</strong> <span id="watchlist-summary"></span></p>
    <div id="watchlist-alerts" class="src-chips"></div>
  </div>
  <div class="grid" id="watchlist-grid" style="margin-top:1rem"></div>
</div>

<button class="help-fab" type="button" onclick="toggleHelpPanel()" title="Shortcuts help">?</button>
<div class="help-panel" id="help-panel">
  <div class="help-title">Keyboard Shortcuts</div>
  <div class="help-row"><span>Recommend mode</span><b>Alt+1</b></div>
  <div class="help-row"><span>Movie mode</span><b>Alt+2</b></div>
  <div class="help-row"><span>Actor mode</span><b>Alt+3</b></div>
  <div class="help-row"><span>Character mode</span><b>Alt+4</b></div>
  <div class="help-row"><span>Timeline mode</span><b>Alt+5</b></div>
  <div class="help-row"><span>Compare mode</span><b>Alt+6</b></div>
  <div class="help-row"><span>Focus search</span><b>Alt+F</b></div>
  <div class="help-row"><span>Run search</span><b>Alt+S</b></div>
</div>

<script>
// ── LLM STATUS ──────────────────────────────────────────────────────────
async function loadLLMStatus() {
  try {
    const d = await (await fetch('/api/llm-status')).json();
    const bar = document.getElementById('llm-bar');
    let h = '';
    if (d.groq_configured && !d.groq_in_backoff)
      h += `<span class="llm-chip chip-groq"><span class="dot dot-p"></span>${d.active_llm}</span>`;
    else if (d.groq_in_backoff)
      h += `<span class="llm-chip chip-warn"><span class="dot dot-o"></span>Groq rate-limited</span>`;
    if (d.ollama_available)
      h += `<span class="llm-chip chip-ollama"><span class="dot dot-g"></span>Ollama · ${d.ollama_model}</span>`;
    bar.innerHTML = h;
  } catch(e) {}
}
loadLLMStatus();

// ── TRENDING ─────────────────────────────────────────────────────────────
async function loadTrending() {
  try {
    const d = await (await fetch('/api/trending')).json();
    const sec = document.getElementById('trending-section');
    const movies = document.getElementById('trending-movies');
    const series = document.getElementById('trending-series');
    if (!d.movies.length && !d.series.length) return;
    sec.style.display = 'block';
    d.movies.forEach(m => { movies.insertAdjacentHTML('beforeend', trendingCard(m, 'movie')); });
    d.series.forEach(s => { series.insertAdjacentHTML('beforeend', trendingCard(s, 'series')); });
    const ts = new Date(d.updated_at);
    document.getElementById('trending-updated').textContent = 'Updated ' + ts.toLocaleTimeString();
  } catch(e) {}
}
function trendingCard(m, type) {
  const badge = type === 'series' ? `<span class="t-badge tb-new">Series</span>` : '';
  const img = m.poster ? `<img src="${m.poster}" alt="${m.title}" loading="lazy"/>` : `<div style="aspect-ratio:2/3;background:var(--surface3);display:flex;align-items:center;justify-content:center;font-size:2rem">${type==='series'?'📺':'🎬'}</div>`;
  return `<div class="t-card" onclick="searchByTitle('${escapeQ(m.title)}')">
    ${img}${badge}
    <div class="t-card-overlay">
      <div class="t-card-title">${m.title}</div>
      ${m.rating?`<div class="t-card-rating">⭐ ${m.rating.toFixed(1)}</div>`:''}
    </div>
  </div>`;
}
function escapeQ(s){ return (s||'').replace(/'/g,"\\'"); }
function searchByTitle(title) {
  document.getElementById('pref').value = title;
  setModeById('movie');
  go();
}
loadTrending();
// Auto-refresh trending every hour
setInterval(loadTrending, 3600000);

// ── MODE SWITCHING ───────────────────────────────────────────────────────
const MODE_LABELS = {
  recommend: 'What are you in the mood for?',
  movie: 'Enter movie / series name',
  actor: 'Enter actor or director name',
  character: 'Enter character or franchise name',
  timeline: 'Describe your evening/weekend mood flow',
  compare: 'Enter first movie to compare',
};
const MODE_PLACEHOLDERS = {
  recommend: 'e.g. A dark psychological thriller with mind-bending twists, tense atmosphere like Gone Girl…',
  movie: 'e.g. Vikram, Inception, Breaking Bad…',
  actor: 'e.g. Vijay, Kamal Haasan, Christopher Nolan…',
  character: 'e.g. Batman, Thala Ajith, Spider-Man, Ethan Hunt…',
  timeline: 'e.g. Start light and end intense for a Friday night',
  compare: 'e.g. Interstellar',
};
let currentMode = 'recommend';
let navTrail = [];

function setMode(btn) {
  document.querySelectorAll('.mode-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  currentMode = btn.dataset.mode;
  document.getElementById('main-label').textContent = MODE_LABELS[currentMode];
  document.getElementById('pref').placeholder = MODE_PLACEHOLDERS[currentMode];
  document.getElementById('compare-field').style.display = currentMode === 'compare' ? 'block' : 'none';
  // Movie mode is single deep-detail view.
  document.getElementById('count').value = currentMode === 'movie' ? '1' : document.getElementById('count').value;
}
function setModeById(mode) {
  const btn = document.querySelector(`.mode-tab[data-mode="${mode}"]`);
  if (btn) setMode(btn);
}

function pushTrail(label, mode, query){
  navTrail.push({label, mode, query});
  if(navTrail.length > 6) navTrail = navTrail.slice(-6);
  renderTrail();
}

function renderTrail(){
  const wrap = document.getElementById('breadcrumb-wrap');
  const box = document.getElementById('breadcrumb');
  if(!navTrail.length){
    wrap.style.display = 'none';
    box.innerHTML = '';
    return;
  }
  wrap.style.display = 'block';
  box.innerHTML = navTrail.map((c, i) => `<button class="crumb ${i===navTrail.length-1?'active':''}" onclick="goToTrail(${i})">${c.label}</button>`).join('');
}

function goToTrail(idx){
  const c = navTrail[idx];
  if(!c) return;
  document.getElementById('pref').value = c.query || '';
  setModeById(c.mode || 'recommend');
  go();
}

function toggleHelpPanel(){
  const panel = document.getElementById('help-panel');
  if (!panel) return;
  panel.classList.toggle('open');
}

function toggleType(btn) {
  btn.classList.toggle('active');
  if (![...document.querySelectorAll('.type-btn')].some(b => b.classList.contains('active')))
    btn.classList.add('active');
}
function activeTypes() {
  return [...document.querySelectorAll('.type-btn.active')].map(b => b.dataset.type).join(',');
}

function toggleAdv() {
  const w = document.getElementById('adv-wrap');
  const t = document.getElementById('adv-toggle');
  const open = !w.classList.contains('open');
  w.classList.toggle('open', open);
  t.classList.toggle('open', open);
}

// ── SEARCH ───────────────────────────────────────────────────────────────
async function go() {
  const pref = document.getElementById('pref').value.trim();
  if (!pref) { alert('Please enter your search query!'); return; }
  const btn = document.getElementById('cta');
  btn.disabled = true; btn.textContent = 'SEARCHING…';
  document.getElementById('loader').style.display = 'block';
  document.getElementById('status-bar').style.display = 'none';
  document.getElementById('results-hdr').style.display = 'none';
  document.getElementById('grid').innerHTML = '';

  try {
    let res;
    if (currentMode === 'compare') {
      const pref2 = document.getElementById('pref2').value.trim();
      if (!pref2) throw new Error('Please enter second movie for comparison.');
      res = await fetch('/api/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title_1: pref, title_2: pref2 })
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Compare failed'); }
      const c = await res.json();
      const mapped = {
        status: 'success',
        query_analysis: c.summary,
        total_results: 2,
        execution_time_ms: 0,
        llm_used: 'data',
        search_mode: 'compare',
        sources_used: ['OMDb/IMDb', 'TMDB'],
        recommendations: c.compare.map((d, i) => ({
          rank: i + 1,
          title: d.title,
          content_type: d.content_type || 'movie',
          year: d.year,
          overview: d.overview,
          genres: d.genres || [],
          director: d.director,
          cast: d.cast || [],
          runtime: d.runtime,
          language: d.language,
          awards: d.awards,
          ratings: { imdb: d.imdb_rating, imdb_votes: d.imdb_votes, rotten_tomatoes: d.rt, metacritic: d.metacritic },
          poster_url: d.poster,
          imdb_id: d.imdb_id,
          imdb_url: d.imdb_id ? `https://www.imdb.com/title/${d.imdb_id}/` : null,
          confidence: 1,
          ai_reason: 'Side-by-side comparison',
          critics_reviews: d.critics_reviews || [],
          audience_reviews: d.audience_reviews || [],
          watch_platforms_in: d.platforms_in || [],
          watch_provider_links: d.provider_links_in || [],
          combined_score: d.combined_score,
        }))
      };
      render(mapped);
      return;
    }
    res = await fetch('/api/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        preference: pref,
        watched: document.getElementById('watched').value,
        count: parseInt(document.getElementById('count').value) || 6,
        genres: document.getElementById('genres').value,
        hero_actor: document.getElementById('hero').value,
        character_ref: document.getElementById('charref').value,
        content_types: activeTypes(),
        search_mode: currentMode,
        language: document.getElementById('language').value,
        year_from: parseInt(document.getElementById('yr-from').value) || null,
        year_to: parseInt(document.getElementById('yr-to').value) || null,
        min_imdb: parseFloat(document.getElementById('min-imdb').value) || null,
        min_rotten_tomatoes: parseInt(document.getElementById('min-rt').value) || null,
        min_metacritic: parseInt(document.getElementById('min-mc').value) || null,
      })
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail?.message || e.detail || 'Server error'); }
    render(await res.json());
    pushTrail(currentMode === 'movie' ? 'Movie' : currentMode === 'actor' ? 'Actor' : currentMode === 'character' ? 'Character' : currentMode === 'timeline' ? 'Timeline' : currentMode === 'compare' ? 'Compare' : 'Recommend', currentMode, pref);
    loadLLMStatus();
  } catch(err) {
    document.getElementById('grid').innerHTML = `<div class="error-box">⚠️ ${err.message}</div>`;
  } finally {
    document.getElementById('loader').style.display = 'none';
    btn.disabled = false; btn.textContent = 'FIND MY FILMS';
  }
}

// ── RENDER ───────────────────────────────────────────────────────────────
function render(data) {
  if (data.query_analysis) {
    document.getElementById('ai-summary').textContent = data.query_analysis;
    document.getElementById('exec-t').textContent = `${data.execution_time_ms}ms`;
    document.getElementById('src-chips').innerHTML = (data.sources_used || []).map(s => {
      const c = s.toLowerCase().includes('tmdb') ? 'sc-tmdb' : s.toLowerCase().includes('omdb') ? 'sc-omdb' : 'sc-llm';
      return `<span class="src-chip ${c}">${s}</span>`;
    }).join('');
    document.getElementById('status-bar').style.display = 'block';
  }
  const n = data.total_results;
  const modeLabels = { recommend: 'Recommendations', movie: 'Movie Details', actor: 'Filmography', character: 'Similar Characters', timeline: 'Mood Timeline', compare: 'Comparison' };
  document.getElementById('rh-title').textContent = `${n} ${modeLabels[data.search_mode] || 'Results'}`;
  document.getElementById('rh-sub').textContent = `${data.execution_time_ms}ms · ${data.llm_used}`;
  document.getElementById('results-hdr').style.display = 'flex';

  const grid = document.getElementById('grid');
  data.recommendations.forEach((m, i) => grid.insertAdjacentHTML('beforeend', buildCard(m, i * 80)));
  document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
}

async function addCurrentToWatchlist(){
  const pref = document.getElementById('pref').value.trim();
  if(!pref) return alert('Enter a movie name first.');
  const r = await fetch('/api/watchlist/add', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({title: pref})
  });
  const d = await r.json();
  if(!r.ok) return alert(d.detail || 'Unable to add watchlist');
  alert((d.alerts||['Added'])[0]);
}

async function refreshWatchlistAlerts(){
  const r = await fetch('/api/watchlist/check', {method:'POST'});
  const d = await r.json();
  if(!r.ok) return alert(d.detail || 'Unable to check watchlist');
  loadWatchlist(d);
}

async function loadWatchlist(preloaded=null){
  const d = preloaded || await (await fetch('/api/watchlist')).json();
  const panel = document.getElementById('watchlist-panel');
  const grid = document.getElementById('watchlist-grid');
  const summary = document.getElementById('watchlist-summary');
  const alerts = document.getElementById('watchlist-alerts');
  panel.style.display = 'block';
  summary.textContent = `(${(d.items||[]).length} items)`;
  alerts.innerHTML = (d.alerts||[]).map(a=>`<span class="src-chip sc-tmdb">${a}</span>`).join('');
  grid.innerHTML = '';
  (d.items||[]).forEach((it, idx)=>{
    grid.insertAdjacentHTML('beforeend', buildCard({
      rank: idx+1, title: it.title, poster_url: it.poster_url, content_type:'movie',
      confidence:0.8, ratings:{}, genres:[], cast:[], watch_platforms_in: it.watch_platforms_in || [],
      new_platforms_in: it.new_platforms_in || [],
      watch_provider_links: [], critics_reviews:[], audience_reviews:[], mood_tags:[],
      ai_reason:`Watchlist item · last checked ${it.last_checked_at || ''}`
    }, 0));
  });
}

// ── CARD BUILDER ─────────────────────────────────────────────────────────
const PALETTES = [
  ['#0d0118','#3a0050'],['#01101e','#023a60'],['#1d0008','#5a001a'],
  ['#001808','#004a18'],['#1a0e00','#503000'],['#01081f','#01205a'],
  ['#111100','#3a3a00'],['#110018','#42005a'],['#001010','#003535'],
  ['#1a0808','#5a1010'],['#080818','#18186a'],['#001810','#004a35'],
];
function palette(t) {
  let h = 0;
  for (const c of t) h = (h * 31 + c.charCodeAt(0)) & 0xffffffff;
  return PALETTES[Math.abs(h) % PALETTES.length];
}
function fallbackPoster(m) {
  const [c1, c2] = palette(m.title);
  const icons = { movie: '🎬', series: '📺', short: '🎞️' };
  const short = m.title.length > 22 ? m.title.slice(0, 19) + '…' : m.title;
  return `<div class="poster-fallback" style="background:linear-gradient(160deg,${c1} 0%,${c2} 100%)">
    <div class="pf-icon">${icons[m.content_type] || '🎬'}</div>
    <div class="pf-title">${short}</div>
    ${m.year ? `<div class="pf-year">${m.year}</div>` : ''}
  </div>`;
}
function scoreClass(s) {
  if (!s) return '';
  return s >= 72 ? 'score-hi' : s >= 54 ? 'score-md' : 'score-lo';
}

function buildCard(m, delay) {
  const pct = Math.round((m.confidence || 0) * 100);
  const ctCls = { movie: 'ct-movie', series: 'ct-series', short: 'ct-short' }[m.content_type] || 'ct-movie';
  const ctLbl = { movie: 'Movie', series: 'Series', short: 'Short' }[m.content_type] || 'Movie';
  const iid = m.imdb_id || '';
  const isOllama = (m.llm_source || '').includes('ollama');

  let yearStr = m.year ? String(m.year) : '';
  if (m.content_type === 'series' && m.end_year && m.end_year !== m.year) yearStr += `–${m.end_year}`;

  const directorName = (m.director && m.director !== 'N/A') ? m.director.split(',')[0].trim() : '';
  const creatorName = m.creator ? m.creator.split(',')[0].trim() : '';
  const leadCast = (m.cast || []).slice(0, 4);
  const credit = m.content_type === 'series'
    ? (creatorName ? `Created by <span class="person-link" title="Click to view works" onclick="event.stopPropagation();quickSearchPerson('${escapeQ(creatorName)}')">${creatorName}</span>` : '')
    : (directorName ? `Dir. <span class="person-link" title="Click to view works" onclick="event.stopPropagation();quickSearchPerson('${escapeQ(directorName)}')">${directorName}</span>` : '');
  const castStr = leadCast.map(n => `<span class="person-link" title="Click to view works" onclick="event.stopPropagation();quickSearchPerson('${escapeQ(n)}')">${n}</span>`).join(', ');

  // Poster
  const posterHTML = m.poster_url
    ? `<img src="${m.poster_url}" alt="${m.title}" loading="lazy" onerror="this.outerHTML=\`${fallbackPoster(m).replace(/`/g, '\\`')}\`"/>`
    : fallbackPoster(m);

  // Ratings
  const ratingsHTML = (() => {
    const blocks = [];
    const r = m.ratings || {};
    if (r.imdb && r.imdb !== 'N/A') {
      blocks.push(`<div class="rating-block">
        <div class="rb-ico">⭐</div>
        <div class="rb-val rv-imdb">${r.imdb}</div>
        <div class="rb-lbl">IMDb</div>
        ${r.imdb_votes ? `<div class="votes-lbl">${r.imdb_votes}</div>` : ''}
      </div>`);
    }
    if (r.rotten_tomatoes) {
      blocks.push(`<div class="rating-block">
        <div class="rb-ico">🍅</div>
        <div class="rb-val rv-rt">${r.rotten_tomatoes}</div>
        <div class="rb-lbl">Rotten Tomatoes</div>
      </div>`);
    }
    if (r.metacritic) {
      blocks.push(`<div class="rating-block">
        <div class="rb-ico">🎯</div>
        <div class="rb-val rv-mc">${r.metacritic}</div>
        <div class="rb-lbl">Metacritic</div>
      </div>`);
    }
    return blocks.length ? `<div class="ratings-row">${blocks.join('')}</div>` : '';
  })();

  // Genres
  const genresHTML = (m.genres || []).slice(0, 5).map(g => `<span class="genre-tag">${g}</span>`).join('');

  // Watch platforms in India
  const platforms = (m.watch_platforms_in || []).slice(0, 6).join(' · ');
  const providerLinks = (m.watch_provider_links || []).slice(0, 6);
  const providerLogoMap = {
    'netflix': 'https://upload.wikimedia.org/wikipedia/commons/0/08/Netflix_2015_logo.svg',
    'amazon prime video': 'https://upload.wikimedia.org/wikipedia/commons/f/f1/Prime_Video.png',
    'prime video': 'https://upload.wikimedia.org/wikipedia/commons/f/f1/Prime_Video.png',
    'disney plus hotstar': 'https://upload.wikimedia.org/wikipedia/commons/1/1e/Disney%2B_Hotstar_logo.svg',
    'hotstar': 'https://upload.wikimedia.org/wikipedia/commons/1/1e/Disney%2B_Hotstar_logo.svg',
    'zee5': 'https://upload.wikimedia.org/wikipedia/commons/8/8e/ZEE5_logo.svg',
    'sony liv': 'https://upload.wikimedia.org/wikipedia/commons/7/7a/SonyLIV_logo.svg',
    'jiocinema': 'https://upload.wikimedia.org/wikipedia/commons/5/59/JioCinema_logo.svg',
    'apple tv plus': 'https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg',
    'youtube': 'https://upload.wikimedia.org/wikipedia/commons/b/b8/YouTube_Logo_2017.svg',
    'mx player': 'https://upload.wikimedia.org/wikipedia/commons/3/3f/MX_Player_logo.svg'
  };
  const providerEmojiMap = {
    'netflix': '🎬',
    'amazon prime video': '📦',
    'prime video': '📦',
    'disney plus hotstar': '⭐',
    'hotstar': '⭐',
    'zee5': '🟣',
    'sony liv': '📺',
    'jiocinema': '🎥',
    'apple tv plus': '🍎',
    'youtube': '▶️',
    'mx player': '🎞️'
  };
  const providerIconHTML = (name) => {
    const key = (name || '').toLowerCase();
    const logo = providerLogoMap[key];
    if (logo) return `<img class="provider-logo" src="${logo}" alt="${name}" loading="lazy" onerror="this.replaceWith(document.createElement('span'));this.nextSibling&&this.nextSibling.remove();"/>`;
    return `<span class="provider-emoji">${providerEmojiMap[key] || '📺'}</span>`;
  };
  const providerLinksHTML = providerLinks.length
    ? `<div class="provider-links">${providerLinks.map(p =>
        p.url
          ? `<a class="provider-link" href="${p.url}" target="_blank" rel="noopener">${providerIconHTML(p.name)}<span>${p.name}</span></a>`
          : `<span class="provider-link">${providerIconHTML(p.name)}<span>${p.name}</span></span>`
      ).join('')}</div>`
    : '';
  const platformsHTML = `<div class="platforms-row">
    <span class="platforms-lbl">📺 India</span>
    ${providerLinksHTML || (platforms ? `<span class="platforms-list">${platforms}</span>` : `<span class="platforms-empty">Provider data not available for this title in India yet.</span>`)}
  </div>`;

  // Compact IMDb + Rotten badges near ratings context
  const miniRatingsHTML = (() => {
    const r = m.ratings || {};
    const chips = [];
    if (r.imdb && r.imdb !== 'N/A') {
      chips.push(`<span class="mini-chip imdb"><span class="icon">⭐</span><span class="label">imdb</span><strong>${r.imdb}/10</strong></span>`);
    }
    if (r.rotten_tomatoes) {
      chips.push(`<span class="mini-chip rt"><span class="icon">🍅</span><span class="label">rt</span><strong>${r.rotten_tomatoes}</strong></span>`);
    }
    return chips.length ? `<div class="mini-ratings">${chips.join('')}</div>` : '';
  })();

  // Critics reviews
  const criticsHTML = (m.critics_reviews || []).slice(0, 2).map(rv =>
    `<div class="review-item review-critic">
      <div class="rv-author">
        ✍️ ${rv.author || 'Critic'}
        ${rv.rating ? `<span class="rv-rating-badge">★ ${rv.rating}</span>` : ''}
      </div>
      <div class="rv-text">${rv.content || ''}</div>
    </div>`
  ).join('');

  // Audience reviews
  const audienceHTML = (m.audience_reviews || []).slice(0, 2).map(rv =>
    `<div class="review-item review-audience">
      <div class="rv-author">👤 ${rv.author || 'Viewer'}${rv.rating ? ` <span class="rv-rating-badge">★ ${rv.rating}</span>` : ''}</div>
      <div class="rv-text">${rv.content || ''}</div>
    </div>`
  ).join('');

  const reviewsSection = `<div class="reviews-section">
    <div class="review-hdr">🎬 Critics Review</div>
    ${criticsHTML || `<div class="review-item review-critic"><div class="rv-text">${m.best_review || 'Critic review unavailable for this title.'}</div></div>`}
    <div class="review-hdr">👥 Audience Review</div>
    ${audienceHTML || `<div class="review-item review-audience"><div class="rv-text">${m.best_review || 'Audience review unavailable for this title.'}</div></div>`}
  </div>`;

  // AI block
  const whyHTML = (m.why_matches || []).map(r => `<li>${r}</li>`).join('');
  const similarList = (m.similar_titles || []).slice(0, 6);
  const similarLinksHTML = similarList.length
    ? `<div class="sim-links">${similarList.map(t => `<span class="sim-chip" onclick="event.stopPropagation();quickSearchSimilar('${escapeQ(t)}')">${t}</span>`).join('')}</div>`
    : '';
  const aiBlock = (m.ai_reason || whyHTML || m.similar_to) ? `<div class="ai-block">
    ${m.ai_reason ? `<div class="ai-reason">${m.ai_reason}</div>` : ''}
    ${whyHTML ? `<ul class="why-list">${whyHTML}</ul>` : ''}
    ${m.similar_to ? `<div class="c-similar">💡 ${m.similar_to}</div>` : ''}
    ${similarLinksHTML}
  </div>` : '';

  // Best review (if no structured reviews)
  const bestReviewHTML = (!criticsHTML && !audienceHTML && m.best_review) ? `<div class="reviews-section">
    <div class="review-item review-audience">
      <div class="rv-text">${m.best_review}</div>
    </div>
  </div>` : '';

  // Actor bio (rank 1 actor search)
  const actorBioHTML = m.actor_bio ? `<div class="actor-bio-block">
    <div class="actor-bio-text">${m.actor_bio}</div>
    ${(m.known_for || []).length ? `<div class="known-for-list">Known for: ${m.known_for.join(', ')}</div>` : ''}
  </div>` : '';

  // Character badge
  const charBadgeHTML = m.character_name ? `<span class="char-badge">🦸 ${m.character_name}</span>` : '';

  // Awards
  const awardsHTML = m.awards && m.awards !== 'N/A' ? `<div class="awards-row">🏆 ${m.awards.slice(0, 80)}</div>` : '';

  // Mood tags
  const moodsHTML = (m.mood_tags || []).length ? `<div class="mood-tags">${(m.mood_tags || []).map(t => `<span class="mood-tag">${t}</span>`).join('')}</div>` : '';
  const newOttHTML = (m.new_platforms_in || []).length
    ? `<div class="new-ott-row">${(m.new_platforms_in || []).slice(0,4).map(p => `<span class="new-ott-badge">🆕 ${p}</span>`).join('')}</div>`
    : '';

  const seasons = m.seasons ? `${m.seasons} season${m.seasons !== 1 ? 's' : ''}` : '';
  const detailsId = `details-${(m.imdb_id || m.title || '').replace(/[^a-zA-Z0-9]/g, '').slice(0, 24)}-${m.rank}`;

  return `<div class="card" style="animation-delay:${delay}ms">
    <div class="poster-wrap">
      <div class="poster-img-area" onclick="toggleCardDetails('${detailsId}')">${posterHTML}</div>
      <div class="poster-overlays">
        <span class="ov-rank">#${m.rank}</span>
        <span class="ov-match">${pct}% match</span>
        <span class="ov-ct ${ctCls}">${ctLbl}</span>
        ${m.combined_score ? `<span class="ov-score ${scoreClass(m.combined_score)}">${m.combined_score}<span style="font-size:.58rem;opacity:.7">/100</span></span>` : ''}
        ${isOllama ? `<span class="ov-llm">✦ Mistral</span>` : ''}
      </div>
    </div>
    <div class="cbody">
      <div class="c-title-row">
        <div class="c-title">${m.title}</div>
        ${yearStr ? `<div class="c-year">${yearStr}</div>` : ''}
      </div>
      ${charBadgeHTML}
      ${(credit || castStr || m.runtime || seasons) ? `<div class="c-meta">
        ${credit ? `<span>${credit}</span>` : ''}
        ${castStr ? `${credit ? '<span class="c-dot">·</span>' : ''}<span>${castStr}</span>` : ''}
        ${m.runtime ? `<span class="c-dot">·</span><span>${m.runtime}</span>` : ''}
        ${seasons ? `<span class="c-dot">·</span><span>${seasons}</span>` : ''}
        ${m.language ? `<span class="c-dot">·</span><span>${m.language}</span>` : ''}
      </div>` : ''}
      ${genresHTML ? `<div class="c-genres">${genresHTML}</div>` : ''}
      ${ratingsHTML}
      ${miniRatingsHTML}
      ${platformsHTML}
      ${m.overview ? `<div class="c-overview">${m.overview}</div>` : ''}
      <div class="tap-hint">Tap poster to view reviews & deep insights</div>
      ${awardsHTML}
      <div id="${detailsId}" class="details-panel">
        ${actorBioHTML}
        ${reviewsSection}
        ${bestReviewHTML}
        ${aiBlock}
      </div>
      ${moodsHTML}
      ${newOttHTML}
      ${m.imdb_url ? `<a class="imdb-link" href="${m.imdb_url}" target="_blank" rel="noopener">⭐ View on IMDb</a>` : ''}
    </div>
  </div>`;
}

function toggleCardDetails(id){
  const el = document.getElementById(id);
  if(!el) return;
  el.classList.toggle('open');
}

function quickSearchPerson(name){
  document.getElementById('pref').value = name;
  setModeById('actor');
  pushTrail('Actor', 'actor', name);
  go();
}

function quickSearchSimilar(title){
  document.getElementById('pref').value = `movies similar to ${title}`;
  setModeById('recommend');
  pushTrail('Similar', 'recommend', `movies similar to ${title}`);
  go();
}

// Power-user shortcuts
document.addEventListener('keydown', (e) => {
  if (!e.altKey) return;
  const k = e.key;
  if (k === '1') { e.preventDefault(); setModeById('recommend'); return; }
  if (k === '2') { e.preventDefault(); setModeById('movie'); return; }
  if (k === '3') { e.preventDefault(); setModeById('actor'); return; }
  if (k === '4') { e.preventDefault(); setModeById('character'); return; }
  if (k === '5') { e.preventDefault(); setModeById('timeline'); return; }
  if (k === '6') { e.preventDefault(); setModeById('compare'); return; }
  if (k.toLowerCase() === 'f') { e.preventDefault(); document.getElementById('pref').focus(); return; }
  if (k.toLowerCase() === 's') { e.preventDefault(); go(); return; }
});

document.getElementById('pref').addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) go();
});
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    logger.info("🎬  CineAI v6 → http://localhost:8000")
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)