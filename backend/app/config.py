from __future__ import annotations
import os
from dataclasses import dataclass


def _int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int(os.environ.get(name, default))
    except ValueError:
        v = default
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class Settings:
    app_version: str = "0.1.0"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma3:4b"
    ollama_timeout: int = 90
    max_upload_mb: int = 10
    max_messages_per_import: int = 5000
    max_messages_per_batch: int = 20
    session_ttl_minutes: int = 60
    default_event_minutes: int = 30
    demo_mode: bool = False
    allowed_origins: tuple = ("http://127.0.0.1:8000", "http://localhost:8000",
                              "http://127.0.0.1:5173", "http://localhost:5173")


def load_settings() -> Settings:
    e = os.environ
    return Settings(
        ollama_base_url=e.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollama_model=e.get("OLLAMA_MODEL", "gemma3:4b"),
        ollama_timeout=_int("OLLAMA_TIMEOUT_SECONDS", 90, 5, 600),
        max_upload_mb=_int("MAX_UPLOAD_MB", 10, 1, 50),
        max_messages_per_import=_int("MAX_MESSAGES_PER_IMPORT", 5000, 10, 50000),
        max_messages_per_batch=_int("MAX_MESSAGES_PER_BATCH", 20, 1, 50),
        session_ttl_minutes=_int("SESSION_TTL_MINUTES", 60, 1, 1440),
        default_event_minutes=_int("DEFAULT_EVENT_MINUTES", 30, 5, 480),
        demo_mode=e.get("DEMO_MODE", "false").lower() in ("1", "true", "yes"),
    )
