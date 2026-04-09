"""
config.py — Research run configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResearchConfig:
    topic: str = "AI/ML enterprise software"
    days: int = 7
    region: str = "global"
    max_items: int = 10
    output_dir: Path = field(default_factory=lambda: Path("./output"))

    # Reliability settings
    fetch_retries: int = 3
    retry_backoff_seconds: float = 2.0
    request_timeout_seconds: int = 15
