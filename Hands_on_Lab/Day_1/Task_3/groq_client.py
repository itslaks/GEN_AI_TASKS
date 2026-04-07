"""
groq_client.py — Thin Groq API wrapper with retries, timeouts, and env config.
"""

import os
import time
import json
import logging
import urllib.request
import urllib.error
from typing import Any

log = logging.getLogger(__name__)

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT = 60
MAX_RETRIES = 3
RETRY_DELAY = 2.0  # seconds, doubled on each retry


def chat(
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """Send chat messages to Groq, return the assistant text."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY environment variable is not set.")

    payload = json.dumps({
        "model": GROQ_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": messages,
    }).encode()

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    delay = RETRY_DELAY
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(GROQ_URL, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code == 401:
                raise RuntimeError("Invalid GROQ_API_KEY (401 Unauthorized).") from e
            if e.code == 429:
                log.warning("Rate limit hit (attempt %d). Retrying in %.1fs…", attempt, delay)
            else:
                log.warning("HTTP %d on attempt %d: %s", e.code, attempt, body[:200])
        except TimeoutError:
            log.warning("Groq request timed out (attempt %d).", attempt)
        except Exception as e:
            log.warning("Unexpected error on attempt %d: %s", attempt, e)

        if attempt < MAX_RETRIES:
            time.sleep(delay)
            delay *= 2

    raise RuntimeError(f"Groq API failed after {MAX_RETRIES} attempts.")