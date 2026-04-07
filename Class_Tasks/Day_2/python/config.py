"""
Configuration for CineAI v5 — with Ollama/Mistral fallback support.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
CACHE_DIR = PROJECT_ROOT / "cache"

for d in [DATA_DIR, LOGS_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    # ── Groq (primary LLM — free tier) ───────────────────────────────────
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    # ── Ollama (local fallback — Mistral) ─────────────────────────────────
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "mistral:latest")

    # ── OMDb (ratings + posters — free 1000/day) ─────────────────────────
    omdb_api_key: str = os.getenv("OMDB_API_KEY", "")

    # ── TMDB (optional — extra poster source) ────────────────────────────
    tmdb_api_key: str = os.getenv("TMDB_API_KEY", "")

    # ── App ───────────────────────────────────────────────────────────────
    app_env: str = os.getenv("APP_ENV", "development")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    # ── LLM ───────────────────────────────────────────────────────────────
    llm_temperature: float = 0.25
    llm_max_tokens: int = 800        # Tight — avoids Groq 413 errors
    llm_timeout: int = 45

    # ── Cache ─────────────────────────────────────────────────────────────
    cache_ttl_seconds: int = 7200    # 2 hours
    cache_dir: str = str(CACHE_DIR)
    data_dir: str = str(DATA_DIR)
    logs_dir: str = str(LOGS_DIR)

    class Config:
        env_file = PROJECT_ROOT / ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()

PATHS = {
    "root": str(PROJECT_ROOT),
    "data": str(DATA_DIR),
    "logs": str(LOGS_DIR),
    "cache": str(CACHE_DIR),
}


if __name__ == "__main__":
    print("\n" + "="*55)
    print("🎬  CineAI v5 — CONFIG CHECK")
    print("="*55)
    print(f"  {'✓' if settings.groq_api_key else '✗'} GROQ_API_KEY  (groq.com/console)")
    print(f"  {'✓' if settings.omdb_api_key else '✗'} OMDB_API_KEY  (omdbapi.com/apikey.aspx)")
    print(f"  {'✓' if settings.tmdb_api_key else '~'} TMDB_API_KEY  (optional poster fallback)")
    print(f"  ✓ Ollama URL  : {settings.ollama_base_url}")
    print(f"  ✓ Ollama Model: {settings.ollama_model}")
    print(f"  ✓ Groq Model  : {settings.groq_model}")
    print(f"  ✓ Max Tokens  : {settings.llm_max_tokens} (Groq free-tier safe)")
    print("="*55)