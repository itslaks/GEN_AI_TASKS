"""
Configuration for CineAI v6 — Enhanced with all features.
"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
CACHE_DIR = PROJECT_ROOT / "cache"

for d in [DATA_DIR, LOGS_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    # ── Groq (primary LLM — free tier) ───────────────────────────────────
    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.1-8b-instant")

    # ── Ollama (local fallback — Mistral) ─────────────────────────────────
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="mistral:latest")

    # ── OMDb (ratings + posters — free 1000/day) ─────────────────────────
    omdb_api_key: str = Field(default="")

    # ── TMDB (optional — extra poster source, watch providers) ────────────
    tmdb_api_key: str = Field(default="")

    # ── App ───────────────────────────────────────────────────────────────
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # ── LLM ───────────────────────────────────────────────────────────────
    llm_temperature: float = 0.25
    llm_max_tokens: int = 800
    llm_timeout: int = 45
    # Similarity strictness for "movies like X" queries (0-100).
    similarity_min_threshold: float = Field(default=35.0, ge=0.0, le=100.0)

    # ── Security ─────────────────────────────────────────────────────────
    rate_limit_ip_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_ip_max_requests: int = Field(default=120, ge=1, le=5000)
    rate_limit_user_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_user_max_requests: int = Field(default=80, ge=1, le=5000)
    max_input_chars: int = Field(default=397, ge=32, le=397)

    # ── Cache ─────────────────────────────────────────────────────────────
    cache_ttl_seconds: int = 7200
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
    print("\n" + "=" * 55)
    print("🎬  CineAI v6 — CONFIG CHECK")
    print("=" * 55)
    print(f"  {'✓' if settings.groq_api_key else '✗'} GROQ_API_KEY  (groq.com/console)")
    print(f"  {'✓' if settings.omdb_api_key else '✗'} OMDB_API_KEY  (omdbapi.com/apikey.aspx)")
    print(f"  {'✓' if settings.tmdb_api_key else '~'} TMDB_API_KEY  (optional poster + watch providers)")
    print(f"  ✓ Ollama URL  : {settings.ollama_base_url}")
    print(f"  ✓ Ollama Model: {settings.ollama_model}")
    print(f"  ✓ Groq Model  : {settings.groq_model}")
    print("=" * 55)