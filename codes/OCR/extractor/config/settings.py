"""
Configuration and settings module for the Willow food safety analysis backend.
Loads environment variables and sets defaults for Gemini API, models, and timeouts.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Search for .env files up the directory tree
_current_dir = Path(__file__).resolve().parent
_search_dirs = [
    _current_dir,
    _current_dir.parent,
    _current_dir.parent.parent,
    _current_dir.parent.parent.parent,
]

for d in _search_dirs:
    env_file = d / ".env"
    if env_file.is_file():
        load_dotenv(env_file)
        break

# Configure logger
logger = logging.getLogger("willow.gemini")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())


class Settings:
    """Application and Gemini API settings."""

    # Gemini API Credentials
    GEMINI_API_KEY: str | None = os.environ.get("GEMINI_API_KEY")

    # Configurable Gemini Model
    GEMINI_ANALYSIS_MODEL: str = os.environ.get(
        "GEMINI_ANALYSIS_MODEL",
        os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    )

    # Request Timeout and Retries
    GEMINI_REQUEST_TIMEOUT: float = float(os.environ.get("GEMINI_REQUEST_TIMEOUT", "30.0"))
    GEMINI_MAX_RETRIES: int = int(os.environ.get("GEMINI_MAX_RETRIES", "3"))

    @classmethod
    def get_api_key(cls) -> str | None:
        """Returns the loaded API key without logging or exposing it."""
        return cls.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")

    @classmethod
    def has_api_key(cls) -> bool:
        """Checks if a valid API key is configured."""
        key = cls.get_api_key()
        return bool(key and key.strip())


settings = Settings()

