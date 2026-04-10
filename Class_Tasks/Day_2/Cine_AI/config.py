"""
CineAI — Configuration
"""
from __future__ import annotations
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # API Keys
    groq_api_key: str = ""
    omdb_api_key: str = ""
    tmdb_api_key: str = ""

    # LLM config
    groq_model: str = "llama-3.1-8b-instant"
    ollama_model: str = "mistral"
    ollama_base_url: str = "http://localhost:11434"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: str = "INFO"

    # Limits
    max_input_chars: int = 500
    rate_limit_ip_max_requests: int = 30
    rate_limit_ip_window_seconds: int = 60

    # Cache
    cache_dir: str = ""
    cache_ttl_seconds: int = 3600
    data_dir: str = ""

    # Similarity
    similarity_min_threshold: float = 20.0

    def __init__(self, **values):
        super().__init__(**values)
        is_vercel = os.environ.get("VERCEL") == "1"
        if is_vercel:
            self.cache_dir = "/tmp/cache"
            self.data_dir = "/tmp/data"
        else:
            if not self.cache_dir:
                self.cache_dir = str(BASE_DIR / "cache")
            if not self.data_dir:
                self.data_dir = str(BASE_DIR / "data")


PATHS = {
    "base": BASE_DIR,
}

settings = Settings()

# Ensure directories exist (wrapped in try-except for environments with restricted filesystem)
try:
    Path(settings.cache_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    PATHS["cache"] = Path(settings.cache_dir)
    PATHS["data"] = Path(settings.data_dir)
except Exception:
    # If this fails, we assume we're in a highly restricted environment
    # and will rely on the app logic to handle missing directories if possible
    pass
