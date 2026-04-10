"""
CineAI — Smart Movie Discovery Engine
======================================
Features:
  • AI-powered mood/genre recommendations with weighted scoring
    (IMDb 35% + Rotten Tomatoes 25% + Metacritic 20% + Audience 20%)
  • Direct movie search → full details, posters, reviews, OTT platforms
  • "Movies like X" — thematic/emotional similarity engine
  • 2-movie head-to-head comparison
  • Actor/Director filmography search
  • Character archetype discovery
  • Mood Timeline: light→intense session planner
  • Watchlist with OTT change alerts
  • Groq LLM / llama-3.1-8b-instant (primary) + Ollama/Mistral (fallback)
  • OWASP-aligned security, rate limiting, input sanitisation
"""
from __future__ import annotations

import asyncio
import html
import hashlib
import json
import logging
import math
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
logger.info("🚀 CineAI Engine is warming up...")



# ══════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════════

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
    source: Optional[str] = None


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
    weighted_score: Optional[float] = None
    llm_source: str = "groq"
    actor_bio: Optional[str] = None
    known_for: list[str] = []
    character_name: Optional[str] = None
    similar_characters: list[str] = []
    new_platforms_in: list[str] = []


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


def _coerce_review(rv) -> Optional["ReviewItem"]:
    """Safely coerce a review value to ReviewItem regardless of its current type."""
    if rv is None:
        return None
    if isinstance(rv, ReviewItem):
        return rv
    if isinstance(rv, dict):
        try:
            return ReviewItem(**{k: v for k, v in rv.items() if k in ("author", "content", "rating", "source")})
        except Exception:
            return None
    # It's a string representation or something else — skip it
    return None


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


# ══════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ══════════════════════════════════════════════════════════════════════════

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
    ip_ok, ip_retry = rate_limiter.check(
        ip_key,
        settings.rate_limit_ip_max_requests,
        settings.rate_limit_ip_window_seconds,
    )
    if not ip_ok:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "retry_after_seconds": ip_retry},
            headers={"Retry-After": str(ip_retry)},
        )


# ══════════════════════════════════════════════════════════════════════════
# LLM MANAGER  — Fixed: ChatGroq uses `model` not `model_name`
# ══════════════════════════════════════════════════════════════════════════

class LLMManager:
    # Only string tokens work with `in str(exc)`
    GROQ_RATE_TOKENS = ("rate_limit_exceeded", "Request too large", "413", "429")

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
                model=settings.groq_model,          # Fixed: was model_name
                temperature=0.25,
                max_tokens=800,
                timeout=30,                         # Fixed: was request_timeout
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
        # Fixed: convert all tokens to str for safe `in` check
        exc_str = str(exc)
        return any(token in exc_str for token in self.GROQ_RATE_TOKENS)

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


# ══════════════════════════════════════════════════════════════════════════
# PROMPTS
# ══════════════════════════════════════════════════════════════════════════

INTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a world-class film expert covering ALL major cinema industries:
- Kollywood (Tamil) e.g. Mani Ratnam, Pa. Ranjith, Shankar, K. V. Anand, Vetrimaaran
- Bollywood (Hindi) e.g. Sanjay Leela Bhansali, Imtiaz Ali, Farhan Akhtar
- Hollywood e.g. Nolan, Spielberg, Fincher, Villeneuve
- Mollywood (Malayalam) e.g. Lijo Jose Pellissery, Fahadh Faasil films
- Tollywood (Telugu) e.g. S. S. Rajamouli, Trivikram Srinivas
- Sandalwood (Kannada) e.g. Pawan Kumar, Rishab Shetty
- Korean, Japanese, French, Spanish cinema

Extract intent and return JSON ONLY (no markdown, no explanation):
{{"genres":[],"moods":[],"themes":[],"language":null,"hero_actor":null,"avoid":[],"titles":["T1","T2","T3","T4","T5","T6","T7","T8","T9","T10","T11","T12"],"summary":"one sentence"}}

Rules for titles:
- Return 12 REAL, verifiable movie/show titles that best match the request
- If a regional language is mentioned, heavily favour that language (at least 8 of 12 titles from that industry)
- For Tamil romance, include classics like: Kandukondain Kandukondain, Alaipayuthey, OK Kanmani, 96, Kaathu Vaakula Rendu Kaadhal, Vinnaithaandi Varuvaayaa, Minnale, Autograph, Ninaithale Inikkum, Kadal
- For Bollywood romance: Dilwale Dulhania Le Jayenge, Dil Chahta Hai, Jab We Met, Kal Ho Na Ho, Kapoor & Sons
- For Telugu: Magadheera, Baahubali, Arjun Reddy, Fidaa, Geetha Govindam
- For Malayalam: Premam, Bangalore Days, Charlie, Ohm Shanthi Oshaana, Thattathin Marayathu
- NEVER suggest the same title twice; prioritise variety in style and era
- Include both classics (pre-2000) and contemporary films"""),
    ("human", "Want: {preference}\nSeen: {watched}\nGenres: {genres}\nActor: {hero_actor}\nFranchise: {character_ref}\nTypes: {content_types}\nLanguage: {language}"),
])

RERANK_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a world-class film critic with deep knowledge of Kollywood, Bollywood, Hollywood, Mollywood, Tollywood, Sandalwood, Korean and international cinema.

Pick the best {count} films from the candidates list that best match the user's intent. Return a JSON array ONLY:
[{{"title":"exact title from candidates","confidence":0.9,"ai_reason":"2 compelling sentences why this film fits","why_matches":["reason1","reason2","reason3"],"mood_tags":["tag1","tag2"],"similar_to":"if you liked X","best_review":"one memorable sentence about the film"}}]

Rules:
- ONLY use titles that appear in the candidates list (exact match)
- Rank by relevance to query first, then weighted score
- For regional language queries, strongly prefer films in that language
- Provide diverse results (different directors/eras when possible)
- mood_tags should be emotional descriptors like: sentimental, heartwarming, intense, bittersweet, uplifting, tragic"""),
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

SIMILARITY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Film expert. Given the reference film below, recommend {count} films with SIMILAR:
- Genre and emotional tone
- Story themes and narrative arc
- Character dynamics and relationships
- Period/setting if relevant
Return JSON array only:
[{{"title":"exact movie name","year":2020,"similarity_reason":"2 sentences explaining thematic/emotional connection"}}]"""),
    ("human", "Reference Film: {title}\nGenres: {genres}\nOverview: {overview}\nKey themes: {themes}"),
])

COMPARE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Film critic. Compare these two films head-to-head. Return JSON only:
{{"verdict":"which is better overall and why in 2 sentences","dimensions":[
  {{"label":"Storyline","movie1_score":8,"movie2_score":7,"note":"brief note"}},
  {{"label":"Acting","movie1_score":9,"movie2_score":8,"note":"brief note"}},
  {{"label":"Direction","movie1_score":8,"movie2_score":9,"note":"brief note"}},
  {{"label":"Emotional Impact","movie1_score":7,"movie2_score":8,"note":"brief note"}},
  {{"label":"Entertainment","movie1_score":9,"movie2_score":7,"note":"brief note"}},
  {{"label":"Rewatchability","movie1_score":8,"movie2_score":6,"note":"brief note"}}
]}}"""),
    ("human", "Film 1: {title1} ({year1}) — {overview1}\nFilm 2: {title2} ({year2}) — {overview2}"),
])


# ══════════════════════════════════════════════════════════════════════════
# MEDIA CLIENT
# ══════════════════════════════════════════════════════════════════════════

class MediaClient:
    OMDB = "https://www.omdbapi.com"
    TMDB_SEARCH = "https://api.themoviedb.org/3/search/multi"
    TMDB_IMG = "https://image.tmdb.org/t/p/w500"
    TMDB_FIND = "https://api.themoviedb.org/3/find"
    TMDB_TRENDING = "https://api.themoviedb.org/3/trending"
    TMDB_PERSON = "https://api.themoviedb.org/3/search/person"

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=12, follow_redirects=True)

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
            params: dict[str, Any] = {"api_key": settings.tmdb_api_key, "query": title}
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

    async def watch_provider_payload_in(self, imdb_id: Optional[str]) -> tuple[list[str], list[dict[str, str]]]:
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
                author = rv.get("author") or ""
                content = (rv.get("content") or "").strip().replace("\n", " ")
                if not content:
                    continue
                ad = rv.get("author_details", {})
                rating = str(ad["rating"]) if ad.get("rating") else None
                is_critic = any(
                    x in author.lower()
                    for x in ("critic", "editor", "magazine", "review", "press")
                )
                item = ReviewItem(
                    author=author[:60],
                    content=content[:300],
                    rating=rating,
                    source="critic" if is_critic else "audience",
                )
                if item.source == "critic" and len(critics) < 3:
                    critics.append(item)
                elif len(audience) < 3:
                    audience.append(item)
            return critics, audience
        except Exception:
            return [], []

    async def get_trending(self) -> dict:
        if not settings.tmdb_api_key:
            return {"movies": [], "series": []}
        try:
            movies_r, series_r = await asyncio.gather(
                self._client.get(
                    f"https://api.themoviedb.org/3/movie/now_playing",
                    params={"api_key": settings.tmdb_api_key, "region": "IN"},
                ),
                self._client.get(
                    f"https://api.themoviedb.org/3/tv/on_the_air",
                    params={"api_key": settings.tmdb_api_key},
                ),
            )
            movies = []
            for m in movies_r.json().get("results", [])[:12]:
                movies.append({
                    "title": m.get("title", ""),
                    "year": str(m.get("release_date", ""))[:4],
                    "poster": f"{self.TMDB_IMG}{m['poster_path']}" if m.get("poster_path") else None,
                    "rating": m.get("vote_average"),
                    "overview": (m.get("overview") or "")[:120],
                    "tmdb_id": m.get("id"),
                })
            series = []
            for s in series_r.json().get("results", [])[:12]:
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
            details_r, credits_r = await asyncio.gather(
                self._client.get(
                    f"https://api.themoviedb.org/3/person/{pid}",
                    params={"api_key": settings.tmdb_api_key},
                ),
                self._client.get(
                    f"https://api.themoviedb.org/3/person/{pid}/combined_credits",
                    params={"api_key": settings.tmdb_api_key},
                ),
            )
            details = details_r.json()
            credits = credits_r.json()
            known_for = []
            for c in sorted(
                credits.get("cast", []),
                key=lambda x: x.get("popularity", 0),
                reverse=True,
            )[:10]:
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

    def weighted_score(self, data: dict) -> Optional[float]:
        """
        Weighted composite: IMDb 35% + Rotten Tomatoes 25% + Metacritic 20% + Audience (imdb votes proxy) 20%
        Normalised to 0-100.
        """
        scores: list[float] = []
        weights: list[float] = []

        imdb = data.get("imdbRating", "N/A")
        if imdb and imdb != "N/A":
            try:
                scores.append(float(imdb) * 10)
                weights.append(0.35)
            except ValueError:
                pass

        rt = self.extract_rating(data, "Rotten Tomatoes")
        if rt and "%" in rt:
            try:
                scores.append(float(rt.replace("%", "")))
                weights.append(0.25)
            except ValueError:
                pass

        mc = self.extract_rating(data, "Metacritic")
        if mc and "/" in mc:
            try:
                scores.append(float(mc.split("/")[0]))
                weights.append(0.20)
            except ValueError:
                pass

        votes_raw = data.get("imdbVotes", "N/A")
        if votes_raw and votes_raw != "N/A":
            try:
                votes = int(votes_raw.replace(",", ""))
                audience_score = min(100.0, (math.log10(max(1, votes)) / 6) * 100)
                scores.append(audience_score)
                weights.append(0.20)
            except Exception:
                pass

        if not scores:
            return None
        tw = sum(weights)
        return round(sum(s * w for s, w in zip(scores, weights)) / tw, 1)

    def combined_score(self, data: dict) -> Optional[float]:
        return self.weighted_score(data)

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
            platforms, provider_links, critics_reviews, audience_reviews = [], [], [], []

        seasons_str = data.get("totalSeasons", "")
        writer = (data.get("Writer") or "").strip()
        ws = self.weighted_score(data)
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
            "combined_score": ws,
            "weighted_score": ws,
            "poster": poster if poster and poster != "N/A" else None,
        }


# ══════════════════════════════════════════════════════════════════════════
# FILE CACHE
# ══════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════
# ENGINE
# ══════════════════════════════════════════════════════════════════════════

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
            ws = f" score={e['weighted_score']}" if e.get("weighted_score") else ""
            rel = f" rel={e['relevance_score']}" if e.get("relevance_score") is not None else ""
            imdb = f" imdb={e['imdb_rating']}" if e.get("imdb_rating") else ""
            rt = f" rt={e['rt']}" if e.get("rt") else ""
            lines.append(
                f"- {e['title']} ({e.get('year','?')}){ws}{rel}{imdb}{rt}"
                f" | {(e.get('overview') or '')[:80]}"
            )
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

    def _relevance_score(
        self, req: RecommendationRequest, intent_data: dict, item: dict
    ) -> float:
        concept_map = {
            "love": {"romance", "romantic", "relationship", "couple", "love story"},
            "romance": {"love", "romantic", "relationship", "couple"},
            "funny": {"comedy", "humor", "humour"},
            "sad": {"drama", "emotional", "tragedy"},
            "scary": {"horror", "thriller"},
            "detective": {"mystery", "crime", "thriller"},
            "space": {"sci", "scifi", "science", "fiction"},
            "tamil": {"kollywood", "tamil"},
            "hindi": {"bollywood", "hindi"},
            "telugu": {"tollywood", "telugu"},
            "malayalam": {"mollywood", "malayalam"},
            "kannada": {"sandalwood", "kannada"},
            "kollywood": {"tamil"},
            "bollywood": {"hindi"},
            "mollywood": {"malayalam"},
            "tollywood": {"telugu"},
            "sandalwood": {"kannada"},
        }
        parts = [
            req.preference or "",
            req.genres or "",
            req.hero_actor or "",
            req.language or "",
            " ".join(intent_data.get("genres", [])),
            " ".join(intent_data.get("moods", [])),
            " ".join(intent_data.get("themes", [])),
        ]
        terms: set[str] = set()
        for p in parts:
            for tok in re.split(r"[^a-z0-9]+", p.lower()):
                if len(tok) >= 3:
                    terms.add(tok)
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
            item.get("country", "") or "",
        ]).lower()
        hay_tokens = {t for t in re.split(r"[^a-z0-9]+", hay) if len(t) >= 3}
        token_overlap = len(expanded & hay_tokens) / max(1, len(expanded))

        item_genres = {g.strip().lower() for g in item.get("genres", [])}
        wanted = {g.strip().lower() for g in (intent_data.get("genres", []) or [])}
        wanted.update({g.strip().lower() for g in (req.genres or "").split(",") if g.strip()})
        genre_overlap = len(wanted & item_genres) / max(1, len(wanted)) if wanted else 0.0

        romance_trigger = any(t in expanded for t in ("love", "romance", "romantic", "relationship", "couple"))
        romance_boost = 0.20 if romance_trigger and "romance" in item_genres else 0.0

        # Language match boost
        lang_boost = 0.0
        req_lang = (req.language or intent_data.get("language") or "").lower()
        item_lang = (item.get("language") or "").lower()
        if req_lang and req_lang in item_lang:
            lang_boost = 0.25

        raw = (token_overlap * 0.35) + (genre_overlap * 0.35) + romance_boost + lang_boost
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
        for p in patterns:
            m = re.search(p, q.lower(), flags=re.IGNORECASE)
            if m:
                anchor = q[m.start(1):m.end(1)].strip(" .,:;!?\"'")
                return anchor if anchor else None
        return None

    def _extract_key_themes(self, overview: str) -> str:
        if not overview:
            return ""
        thematic_keywords = {
            "love", "romance", "war", "family", "revenge", "sacrifice",
            "journey", "destiny", "loss", "grief", "hope", "friendship",
            "loyalty", "betrayal", "duty", "honor",
        }
        tokens = {t for t in re.split(r"[^a-z0-9]+", overview.lower()) if len(t) > 3}
        themes = tokens & thematic_keywords
        return ", ".join(sorted(themes)[:5]) if themes else "drama"

    def _anchor_similarity(self, anchor: dict, item: dict) -> float:
        a_genres = {g.lower() for g in anchor.get("genres", [])}
        i_genres = {g.lower() for g in item.get("genres", [])}
        genre_overlap = len(a_genres & i_genres) / max(1, len(a_genres)) if a_genres else 0.0

        a_text = (anchor.get("overview", "") or "").lower()
        i_text = (item.get("overview", "") or "").lower()
        a_tokens = {t for t in re.split(r"[^a-z0-9]+", a_text) if len(t) > 3}
        i_tokens = {t for t in re.split(r"[^a-z0-9]+", i_text) if len(t) > 3}
        emotional_kws = {
            "love", "romance", "romantic", "relationship", "emotional", "war",
            "sacrifice", "duty", "family", "revenge", "journey", "destiny",
            "loss", "grief", "hope", "tragedy",
        }
        a_emo = a_tokens & emotional_kws
        i_emo = i_tokens & emotional_kws
        emo_overlap = len(a_emo & i_emo) / max(1, len(a_emo)) if a_emo else 0.0
        tok_overlap = len(a_tokens & i_tokens) / max(1, len(a_tokens)) if a_tokens else 0.0
        lang_bonus = (
            0.05
            if anchor.get("language")
            and str(anchor.get("language", "")).lower() == str(item.get("language", "")).lower()
            else 0.0
        )
        raw = genre_overlap * 0.45 + emo_overlap * 0.30 + tok_overlap * 0.15 + 0.05 + lang_bonus
        return round(min(1.0, raw) * 100, 1)

    async def _handle_similarity_query(
        self, req: RecommendationRequest, anchor_title: str
    ) -> RecommendationResponse:
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
                lambda llm: SIMILARITY_PROMPT | llm | StrOutputParser(),
                {
                    "title": anchor.get("title", ""),
                    "genres": ", ".join(anchor.get("genres", []))[:120],
                    "overview": (anchor.get("overview") or "")[:220],
                    "themes": self._extract_key_themes(anchor.get("overview", "") or ""),
                    "count": max(req.count * 2, 8),
                },
            )
            parsed = self._parse_json(raw, [])
            similar_titles = [
                x.get("title", "").strip()
                for x in parsed
                if isinstance(x, dict) and x.get("title")
            ]
        except Exception:
            similar_titles = []

        if len(similar_titles) < req.count:
            seeds = await self.media.search(f"{anchor.get('title', '')} movie")
            similar_titles.extend([x.get("Title", "") for x in seeds[:8] if x.get("Title")])

        raw_results = await asyncio.gather(
            *[self.media.enrich(t) for t in similar_titles[:20]],
            return_exceptions=True,
        )
        enriched: list[dict] = []
        seen: set[str] = set()
        anchor_iid = anchor.get("imdb_id")
        for r in raw_results:
            # Fixed: explicit isinstance check instead of treating exceptions as dicts
            if r is None or isinstance(r, Exception):
                continue
            item: dict = r  # type: ignore[assignment]
            iid = item.get("imdb_id") or ""
            title_l = item.get("title", "").lower()
            if (iid and iid == anchor_iid) or title_l in seen:
                continue
            seen.add(title_l)
            sim = self._anchor_similarity(anchor, item)
            if sim < settings.similarity_min_threshold:
                continue
            quality = item.get("weighted_score") or 0.0
            item["similarity_score"] = sim
            item["rank_score"] = round(sim * 0.80 + quality * 0.20, 2)
            enriched.append(item)
        enriched.sort(key=lambda x: x.get("rank_score", 0), reverse=True)

        final: list[MovieCard] = []
        for i, e in enumerate(enriched[:req.count], 1):
            iid = e.get("imdb_id") or ""
            critics_r = [r for r in (_coerce_review(rv) for rv in e.get("critics_reviews", [])) if r is not None]
            audience_r = [r for r in (_coerce_review(rv) for rv in e.get("audience_reviews", [])) if r is not None]
            final.append(MovieCard(
                rank=i,
                title=e["title"],
                content_type=e.get("content_type", "movie"),
                year=e.get("year"),
                end_year=e.get("end_year"),
                overview=e.get("overview"),
                genres=e.get("genres", []),
                director=e.get("director"),
                creator=e.get("creator"),
                cast=e.get("cast", []),
                runtime=e.get("runtime"),
                seasons=e.get("seasons"),
                language=e.get("language"),
                country=e.get("country"),
                awards=e.get("awards"),
                ratings=MovieRatings(
                    imdb=e.get("imdb_rating"),
                    imdb_votes=e.get("imdb_votes"),
                    rotten_tomatoes=e.get("rt"),
                    metacritic=e.get("metacritic"),
                ),
                poster_url=e.get("poster"),
                imdb_id=iid or None,
                imdb_url=f"https://www.imdb.com/title/{iid}/" if iid else None,
                confidence=min(0.95, max(0.70, e.get("similarity_score", 70) / 100)),
                ai_reason=f"Matched to {anchor.get('title')} by genre, story & emotional tone.",
                watch_platforms_in=e.get("platforms_in", []),
                watch_provider_links=e.get("provider_links_in", []),
                critics_reviews=critics_r,
                audience_reviews=audience_r,
                combined_score=e.get("weighted_score"),
                weighted_score=e.get("weighted_score"),
                llm_source=llm_used,
            ))

        return RecommendationResponse(
            status="success",
            query_analysis=f"Movies similar to {anchor.get('title')} by genre, story and emotional tone.",
            recommendations=final,
            total_results=len(final),
            execution_time_ms=round((time.time() - t0) * 1000, 1),
            sources_used=["Similarity Engine", "OMDb/IMDb", "TMDB", f"LLM ({llm_used})"],
            llm_used=llm_used,
            search_mode="recommend",
        )

    async def _seed_titles(
        self, req: RecommendationRequest, llm_titles: list[str]
    ) -> list[tuple[str, Optional[str]]]:
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

        for t in llm_titles[:14]:
            add(t)

        # Build broader search queries including language context
        search_queries = []
        if req.preference:
            search_queries.append(req.preference[:120])
        if req.hero_actor:
            search_queries.append(req.hero_actor[:80])
        if req.genres:
            search_queries.append(req.genres[:80])
        if req.language:
            search_queries.append(f"{req.language} {req.genres or req.preference[:40]}")

        for q in search_queries:
            if not q:
                continue
            try:
                for hit in (await self.media.search(q))[:10]:
                    add(hit.get("Title"), hit.get("imdbID"))
            except Exception:
                pass

        return seeds[:32]

    async def _handle_actor_search(self, req: RecommendationRequest) -> RecommendationResponse:
        t0 = time.time()
        actor_name = req.preference
        person_data = await self.media.search_person(actor_name)
        try:
            raw, llm_used = await llm_manager.invoke(
                lambda llm: ACTOR_PROMPT | llm | StrOutputParser(),
                {"actor_name": actor_name[:100]},
            )
            actor_info = self._parse_json(raw, {})
        except Exception:
            actor_info = {}
            llm_used = "none"

        bio = (person_data or {}).get("bio") or actor_info.get("bio", "")
        known_for_titles = (person_data or {}).get("known_for") or actor_info.get("best_films", [])
        raw_results = await asyncio.gather(
            *[self.media.enrich(t) for t in known_for_titles[:8]],
            return_exceptions=True,
        )
        enriched = []
        seen_iids: set[str] = set()
        for r in raw_results:
            if r is None or isinstance(r, Exception):
                continue
            item: dict = r  # type: ignore[assignment]
            iid = item.get("imdb_id") or ""
            if iid in seen_iids:
                continue
            if iid:
                seen_iids.add(iid)
            enriched.append(item)

        cards = []
        for i, e in enumerate(enriched[:req.count], 1):
            iid = e.get("imdb_id") or ""
            critics_r = [r for r in (_coerce_review(rv) for rv in e.get("critics_reviews", [])) if r is not None]
            audience_r = [r for r in (_coerce_review(rv) for rv in e.get("audience_reviews", [])) if r is not None]
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
                combined_score=e.get("weighted_score"),
                weighted_score=e.get("weighted_score"),
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
        t0 = time.time()
        try:
            raw, llm_used = await llm_manager.invoke(
                lambda llm: CHARACTER_PROMPT | llm | StrOutputParser(),
                {"character_name": req.preference[:100]},
            )
            char_data = self._parse_json(raw, {})
        except Exception:
            char_data = {}
            llm_used = "none"

        similar_chars = char_data.get("similar_characters", [])
        summary = char_data.get("summary", f"Characters similar to {req.preference}")
        tasks = [
            (sc, self.media.enrich(sc.get("movie", "")))
            for sc in similar_chars[:8]
            if sc.get("movie")
        ]
        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
        enriched_cards = []
        for i, (task_pair, result) in enumerate(zip(tasks, results)):
            sc, _ = task_pair
            # Fixed: safe None/Exception check
            e: Optional[dict] = None
            if result is not None and not isinstance(result, Exception):
                e = result  # type: ignore[assignment]
            movie_title = sc.get("movie", "")
            iid = (e or {}).get("imdb_id") or ""
            critics_r = [r for r in (_coerce_review(rv) for rv in (e or {}).get("critics_reviews", [])) if r is not None]
            audience_r = [r for r in (_coerce_review(rv) for rv in (e or {}).get("audience_reviews", [])) if r is not None]
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
                combined_score=(e or {}).get("weighted_score"),
                weighted_score=(e or {}).get("weighted_score"),
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
        t0 = time.time()
        title = req.preference
        data = await self.media.enrich(title)
        if not data:
            results = await self.media.search(title)
            if results:
                data = await self.media.enrich_by_imdb_id(results[0].get("imdbID", ""), title)
        if not data:
            raise HTTPException(status_code=404, detail=f"Movie '{title}' not found.")

        iid = data.get("imdb_id") or ""
        critics_r = [r for r in (_coerce_review(rv) for rv in data.get("critics_reviews", [])) if r is not None]
        audience_r = [r for r in (_coerce_review(rv) for rv in data.get("audience_reviews", [])) if r is not None]

        similar_titles = []
        try:
            raw, llm_used = await llm_manager.invoke(
                lambda llm: FALLBACK_PROMPT | llm | StrOutputParser(),
                {"preference": f"Movies similar to {title}", "count": 5},
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
            combined_score=data.get("weighted_score"),
            weighted_score=data.get("weighted_score"),
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
            sources_used=["OMDb/IMDb", "TMDB"],
            llm_used=llm_used,
            search_mode="movie",
        )

    async def recommend(self, req: RecommendationRequest) -> RecommendationResponse:
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

        day_key = datetime.utcnow().strftime("%Y-%m-%d")
        cache_key = (
            f"intent:{day_key}:{req.preference}:{req.watched}:{req.genres}"
            f":{req.hero_actor}:{req.content_types}:{req.language}"
        )
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
                    },
                )
                intent_data = self._parse_json(raw, {})
                self.cache.set(cache_key, intent_data)
            except Exception as exc:
                logger.error(f"Intent extraction failed: {exc}")
                intent_data = {"titles": [req.preference], "summary": req.preference}

        sources_used.append(f"LLM ({llm_used})")
        suggested_titles = [
            str(t).strip()
            for t in intent_data.get("titles", [req.preference])
            if str(t).strip()
        ]
        summary = intent_data.get("summary", req.preference)

        watched_lower = {w.strip().lower() for w in (req.watched or "").split(",") if w.strip()}

        async def enrich_cached(seed_title: str, seed_imdb_id: Optional[str]) -> Optional[dict]:
            ck = f"omdb:{(seed_imdb_id or seed_title).lower()}"
            cached = self.cache.get(ck)
            if cached is not None:
                return cached
            result = (
                await self.media.enrich_by_imdb_id(seed_imdb_id, seed_title)
                if seed_imdb_id
                else await self.media.enrich(seed_title)
            )
            if result:
                self.cache.set(ck, result)
            return result

        seed_pairs = await self._seed_titles(req, suggested_titles)
        raw_results = await asyncio.gather(
            *[enrich_cached(t, i) for t, i in seed_pairs],
            return_exceptions=True,
        )

        enriched: list[dict] = []
        seen_titles: set[str] = set()
        seen_iids: set[str] = set()
        for r in raw_results:
            if r is None or isinstance(r, Exception):
                continue
            item: dict = r  # type: ignore[assignment]
            key = item["title"].lower()
            iid = (item.get("imdb_id") or "").lower()
            if key in seen_titles or key in watched_lower:
                continue
            if iid and iid in seen_iids:
                continue
            seen_titles.add(key)
            if iid:
                seen_iids.add(iid)
            enriched.append(item)

        enriched = [item for item in enriched if self._passes_filters(req, item)]
        for item in enriched:
            rel = self._relevance_score(req, intent_data, item)
            quality = item.get("weighted_score") or 0.0
            item["relevance_score"] = rel
            item["rank_score"] = round(rel * 0.7 + quality * 0.3, 2)
        enriched.sort(
            key=lambda x: (x.get("rank_score", 0), x.get("weighted_score", 0)),
            reverse=True,
        )

        if settings.omdb_api_key:
            sources_used.append("OMDb/IMDb")
        if settings.tmdb_api_key:
            sources_used.append("TMDB")

        if not enriched:
            try:
                raw, llm_used = await llm_manager.invoke(
                    lambda llm: FALLBACK_PROMPT | llm | StrOutputParser(),
                    {"preference": req.preference[:300], "count": req.count},
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

        candidates_str = self._compact_candidates(enriched[:12])
        intent_compact = (
            f"query:{req.preference[:120]} genres:{intent_data.get('genres', [])} "
            f"moods:{intent_data.get('moods', [])} actor:{intent_data.get('hero_actor', '')}"
        )

        try:
            raw_rank, llm_used2 = await llm_manager.invoke(
                lambda llm: RERANK_PROMPT | llm | StrOutputParser(),
                {
                    "intent": intent_compact[:200],
                    "candidates": candidates_str[:1200],
                    "count": req.count,
                },
            )
            llm_used = llm_used2
            ranked = self._parse_json(raw_rank, [])
        except Exception:
            ranked = [
                {
                    "title": e["title"],
                    "confidence": 0.80,
                    "ai_reason": "",
                    "why_matches": [],
                    "mood_tags": [],
                }
                for e in enriched
            ]

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
            critics_r = [r for r in (_coerce_review(rv) for rv in meta.get("critics_reviews", [])) if r is not None]
            audience_r = [r for r in (_coerce_review(rv) for rv in meta.get("audience_reviews", [])) if r is not None]
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
                combined_score=meta.get("weighted_score"),
                weighted_score=meta.get("weighted_score"),
                llm_source=llm_used,
            ))

        # Fill gaps with remaining enriched items
        if len(final) < req.count:
            for e in enriched:
                iid = e.get("imdb_id") or ""
                if iid and iid in used_iids:
                    continue
                if iid:
                    used_iids.add(iid)
                critics_r = [r for r in (_coerce_review(rv) for rv in e.get("critics_reviews", [])) if r is not None]
                audience_r = [r for r in (_coerce_review(rv) for rv in e.get("audience_reviews", [])) if r is not None]
                final.append(MovieCard(
                    rank=len(final) + 1,
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
                    confidence=0.78,
                    ai_reason="Selected by weighted score ranking.",
                    critics_reviews=critics_r,
                    audience_reviews=audience_r,
                    watch_platforms_in=e.get("platforms_in", []),
                    watch_provider_links=e.get("provider_links_in", []),
                    combined_score=e.get("weighted_score"),
                    weighted_score=e.get("weighted_score"),
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
        base_req = RecommendationRequest(
            **{**req.model_dump(), "search_mode": "recommend", "count": max(req.count, 6)}
        )
        rec = await self.recommend(base_req)

        def intensity(card: MovieCard) -> int:
            text = " ".join([
                card.title or "",
                card.overview or "",
                " ".join(card.genres or []),
                " ".join(card.mood_tags or []),
            ]).lower()
            s = 0
            for t in ("family", "comedy", "romance", "animated", "feel-good"):
                s -= 1 if t in text else 0
            for t in ("war", "horror", "thriller", "violent", "crime", "dark", "action"):
                s += 2 if t in text else 0
            return s

        rec.recommendations = sorted(rec.recommendations, key=intensity)
        for i, card in enumerate(rec.recommendations, 1):
            card.rank = i
            card.ai_reason = (card.ai_reason or "") + (
                " ↑ Light start" if i <= 2 else " ↑ Intense finish"
            )
        rec.query_analysis = f"Mood timeline (light → intense) for: {req.preference}"
        rec.search_mode = "timeline"
        return rec


# ══════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ══════════════════════════════════════════════════════════════════════════

app = FastAPI(title="CineAI", version="2.0.0", docs_url="/docs", redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    _WATCHLIST_FILE.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@app.get("/health", response_model=HealthResponse)
async def health(request: Request):
    _enforce_rate_limits(request)
    ollama_ok = await llm_manager.check_ollama()
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        groq_configured=bool(settings.groq_api_key),
        omdb_configured=bool(settings.omdb_api_key),
        tmdb_configured=bool(settings.tmdb_api_key),
        ollama_available=ollama_ok,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/api/trending", response_model=TrendingResponse)
async def trending(request: Request):
    _enforce_rate_limits(request)
    cache_key = f"trending:{datetime.utcnow().strftime('%Y-%m-%d')}"
    engine = get_engine()
    cached = engine.cache.get(cache_key)
    if cached:
        return TrendingResponse(**cached, updated_at=datetime.utcnow().isoformat() + "Z")
    data = await engine.media.get_trending()
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
        raise HTTPException(
            status_code=404, detail="Unable to resolve one or both movie titles."
        )

    compare_analysis: dict = {}
    try:
        raw, _ = await llm_manager.invoke(
            lambda llm: COMPARE_PROMPT | llm | StrOutputParser(),
            {
                "title1": d1.get("title", ""),
                "year1": d1.get("year", ""),
                "overview1": (d1.get("overview", "") or "")[:200],
                "title2": d2.get("title", ""),
                "year2": d2.get("year", ""),
                "overview2": (d2.get("overview", "") or "")[:200],
            },
        )
        compare_analysis = engine._parse_json(raw, {})
    except Exception:
        compare_analysis = {}

    return {
        "status": "success",
        "compare": [d1, d2],
        "ai_analysis": compare_analysis,
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
        return WatchlistResponse(
            items=[WatchlistItem(**i) for i in items], alerts=["Already in watchlist."]
        )
    items.append({
        "title": data.get("title", payload.title),
        "imdb_id": data.get("imdb_id"),
        "poster_url": data.get("poster"),
        "watch_platforms_in": data.get("platforms_in", []),
        "new_platforms_in": [],
        "last_checked_at": datetime.utcnow().isoformat() + "Z",
    })
    _write_watchlist(items)
    return WatchlistResponse(
        items=[WatchlistItem(**i) for i in items], alerts=["Added to watchlist! ✓"]
    )


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
            alerts.append(f"🎉 {title}: Now on {', '.join(newly_added[:3])} in India!")
        updated.append({
            "title": fresh.get("title", title),
            "imdb_id": fresh.get("imdb_id"),
            "poster_url": fresh.get("poster"),
            "watch_platforms_in": list(new_set),
            "new_platforms_in": newly_added,
            "last_checked_at": datetime.utcnow().isoformat() + "Z",
        })
    _write_watchlist(updated)
    return WatchlistResponse(
        items=[WatchlistItem(**i) for i in updated], alerts=alerts
    )


@app.post("/api/recommend", response_model=RecommendationResponse)
async def recommend(req: RecommendationRequest, request: Request):
    _enforce_rate_limits(request)
    try:
        response = await get_engine().recommend(req)
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
        "active_llm": (
            f"ollama/{settings.ollama_model}"
            if llm_manager.groq_in_backoff()
            else f"groq/{settings.groq_model}"
        ),
    }


@app.get("/manifest.json")
async def manifest():
    manifest_path = Path(__file__).parent / "manifest.json"
    if manifest_path.exists():
        return JSONResponse(content=json.loads(manifest_path.read_text(encoding="utf-8")))
    return JSONResponse(content={"error": "manifest not found"}, status_code=404)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    _enforce_rate_limits(request)
    html_path = Path(__file__).parent / "ui.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<h1>CineAI — UI not found.</h1>", status_code=503
    )


if __name__ == "__main__":
    import uvicorn
    logger.info(f"🎬  CineAI Core → http://127.0.0.1:{settings.port}")
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)