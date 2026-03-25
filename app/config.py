"""
app/config.py — Application configuration

Reads settings from the .env file and exposes them as a typed Settings object.
This is the single source of truth for all configuration in the app.

Why pydantic-settings: it automatically reads environment variables and .env files,
validates types, and gives helpful error messages if required values are missing.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Resolve absolute paths relative to the project root (two levels up from this file)
# Path(__file__) = /path/to/benefitscan/app/config.py
# .parent.parent  = /path/to/benefitscan/
BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    """
    All application settings. Any value here can be overridden by setting
    the corresponding environment variable or adding it to .env.
    """

    # --- AI Provider ---
    # Set AI_PROVIDER to switch between providers without changing any other code.
    # Options: "anthropic" | "gemini"
    # "gemini" is free (no credit card) via aistudio.google.com
    ai_provider: str = "anthropic"

    # --- API Keys (only the one matching your ai_provider is required) ---
    anthropic_api_key: str = ""   # get from console.anthropic.com
    gemini_api_key: str = ""      # get free from aistudio.google.com

    # --- AI Models ---
    claude_model: str = "claude-opus-4-5"    # used when ai_provider=anthropic
    gemini_model: str = "gemini-2.0-flash-lite"  # lightest model, best free-tier availability

    # --- Server ---
    app_port: int = 8000  # 5000 is taken by macOS AirPlay on macOS 12+
    app_env: str = "development"

    # --- Derived paths (computed, not from .env) ---
    # These are properties so they're always relative to wherever the project lives on disk
    @property
    def upload_dir(self) -> Path:
        return BASE_DIR / "storage" / "uploads"

    @property
    def output_dir(self) -> Path:
        return BASE_DIR / "storage" / "outputs"

    @property
    def database_url(self) -> str:
        # SQLite file stored in project root.
        # V2: replace with "postgresql://user:pass@host/db" and change nothing else
        return f"sqlite:///{BASE_DIR / 'benefitscan.db'}"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    # Tell pydantic-settings to read from .env file
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # silently ignore unknown env vars (e.g. system PATH)
    )


# Create a single shared settings instance.
# Import it anywhere with: from app.config import settings
settings = Settings()  # type: ignore[call-arg]
