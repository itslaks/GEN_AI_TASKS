"""
tools.py — Custom CrewAI tools for news fetching.

Sources used (all free, no API key required):
  - Google News RSS  (rss.app mirror / news.google.com)
  - Hacker News Algolia API (public, free)
  - GDELT GKG top-topics endpoint (public domain data)
  - feedparser for general RSS/Atom parsing
"""

import time
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import requests
import feedparser
from crewai.tools import BaseTool
from pydantic import Field

logger = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────────────

def _retry_get(url: str, retries: int = 3, backoff: float = 2.0,
               timeout: int = 15, **kwargs) -> requests.Response | None:
    """GET with exponential back-off; returns None on total failure."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            wait = backoff * (2 ** attempt)
            logger.warning("Attempt %d/%d failed for %s: %s. Retrying in %.1fs",
                           attempt + 1, retries, url, exc, wait)
            if attempt < retries - 1:
                time.sleep(wait)
    logger.error("All %d attempts failed for %s", retries, url)
    return None


def _article_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _parse_date(raw: str | None) -> str:
    """Best-effort ISO date string from feedparser time struct or raw string."""
    if not raw:
        return ""
    try:
        import email.utils
        parsed = email.utils.parsedate_to_datetime(raw)
        return parsed.isoformat()
    except Exception:
        return str(raw)


def _within_window(date_str: str, days: int) -> bool:
    if not date_str:
        return True          # can't filter → keep
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return dt >= cutoff
    except Exception:
        return True


# ── Tool 1: RSS / Google News fetcher ────────────────────────────────────────

class RSSFetcherTool(BaseTool):
    name: str = "rss_news_fetcher"
    description: str = (
        "Fetches recent news articles from RSS/Atom feeds for a given topic. "
        "Input: JSON string with keys 'topic', 'days', 'max_items'. "
        "Returns a JSON list of article dicts: title, publisher, date, url, summary."
    )

    def _run(self, tool_input: str) -> str:
        import json
        try:
            params = json.loads(tool_input)
        except Exception:
            params = {"topic": tool_input, "days": 7, "max_items": 10}

        topic: str = params.get("topic", "AI enterprise software")
        days: int = int(params.get("days", 7))
        max_items: int = int(params.get("max_items", 10))

        encoded = requests.utils.quote(topic)

        feed_urls = [
            # Google News RSS (no key required)
            f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en",
            # Ars Technica AI
            "https://feeds.arstechnica.com/arstechnica/technology-lab",
            # VentureBeat AI
            "https://venturebeat.com/category/ai/feed/",
            # MIT Tech Review
            "https://www.technologyreview.com/feed/",
            # The Verge tech
            "https://www.theverge.com/rss/index.xml",
        ]

        seen: dict[str, dict] = {}
        headers = {"User-Agent": "CrewAI-ResearchBot/1.0"}

        for feed_url in feed_urls:
            if len(seen) >= max_items * 2:
                break
            try:
                resp = _retry_get(feed_url, headers=headers)
                if resp is None:
                    continue
                feed = feedparser.parse(resp.content)
                publisher = feed.feed.get("title", feed_url.split("/")[2])

                for entry in feed.entries:
                    if len(seen) >= max_items * 2:
                        break
                    url = entry.get("link", "")
                    if not url:
                        continue
                    uid = _article_id(url)
                    if uid in seen:
                        continue

                    raw_date = entry.get("published") or entry.get("updated") or ""
                    date_iso = _parse_date(raw_date)
                    if not _within_window(date_iso, days):
                        continue

                    title = entry.get("title", "").strip()
                    # Keyword relevance filter (loose)
                    topic_words = [w.lower() for w in topic.split() if len(w) > 3]
                    text_lower = (title + " " + entry.get("summary", "")).lower()
                    if topic_words and not any(w in text_lower for w in topic_words):
                        continue

                    seen[uid] = {
                        "id": uid,
                        "title": title,
                        "publisher": publisher,
                        "date": date_iso,
                        "url": url,
                        "summary": entry.get("summary", "")[:400],
                    }
            except Exception as exc:
                logger.warning("Feed %s failed: %s", feed_url, exc)
                continue

        articles = list(seen.values())[:max_items]
        return json.dumps(articles, ensure_ascii=False, default=str)


# ── Tool 2: Hacker News (Algolia public API) ─────────────────────────────────

class HackerNewsTool(BaseTool):
    name: str = "hackernews_fetcher"
    description: str = (
        "Fetches recent Hacker News stories relevant to a topic via the free Algolia HN API. "
        "Input: JSON string with keys 'topic', 'days', 'max_items'. "
        "Returns JSON list of article dicts."
    )

    def _run(self, tool_input: str) -> str:
        import json
        try:
            params = json.loads(tool_input)
        except Exception:
            params = {"topic": tool_input, "days": 7, "max_items": 5}

        topic: str = params.get("topic", "AI enterprise software")
        days: int = int(params.get("days", 7))
        max_items: int = int(params.get("max_items", 5))

        cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
        encoded = requests.utils.quote(topic)
        url = (
            f"https://hn.algolia.com/api/v1/search_by_date"
            f"?query={encoded}&tags=story&numericFilters=created_at_i>{cutoff_ts}"
            f"&hitsPerPage={max_items}"
        )

        resp = _retry_get(url)
        if resp is None:
            return json.dumps([])

        data = resp.json()
        articles = []
        for hit in data.get("hits", []):
            story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            articles.append({
                "id": _article_id(story_url),
                "title": hit.get("title", ""),
                "publisher": "Hacker News",
                "date": hit.get("created_at", ""),
                "url": story_url,
                "summary": f"Points: {hit.get('points', 0)}, Comments: {hit.get('num_comments', 0)}",
            })
        return json.dumps(articles, ensure_ascii=False, default=str)


# ── Tool 3: GDELT trending topics (public domain) ────────────────────────────

class GDELTTool(BaseTool):
    name: str = "gdelt_news_fetcher"
    description: str = (
        "Fetches trending technology/AI news articles from GDELT's free public API. "
        "Input: JSON string with keys 'topic', 'max_items'. "
        "Returns JSON list of article dicts."
    )

    def _run(self, tool_input: str) -> str:
        import json
        try:
            params = json.loads(tool_input)
        except Exception:
            params = {"topic": tool_input, "max_items": 5}

        topic: str = params.get("topic", "artificial intelligence enterprise")
        max_items: int = int(params.get("max_items", 5))

        encoded = requests.utils.quote(topic)
        # GDELT DOC 2.0 Article Search (free)
        url = (
            f"https://api.gdeltproject.org/api/v2/doc/doc"
            f"?query={encoded}+sourcelang:english"
            f"&mode=artlist&maxrecords={max_items}&format=json"
            f"&sort=DateDesc&timespan=7d"
        )

        resp = _retry_get(url)
        if resp is None:
            return json.dumps([])

        try:
            data = resp.json()
        except Exception:
            return json.dumps([])

        articles = []
        for art in data.get("articles", []):
            url_a = art.get("url", "")
            articles.append({
                "id": _article_id(url_a),
                "title": art.get("title", ""),
                "publisher": art.get("domain", ""),
                "date": art.get("seendate", ""),
                "url": url_a,
                "summary": art.get("socialimage", ""),
            })
        return json.dumps(articles, ensure_ascii=False, default=str)
