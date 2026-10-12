from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", env_prefix="SANKET_", extra="ignore"
    )
    environment: str = "development"
    database_url: str = "sqlite:///./sanketai.db"
    frontend_origin: str = "http://localhost:5173"
    admin_email: str = "founder@sanketai.local"
    admin_password: str = ""
    secure_cookies: bool = False
    session_hours: int = 12
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    agent_mode: str = "auto"
    max_agent_steps: int = 10
    model_timeout: int = 60
    upload_max_bytes: int = 10 * 1024 * 1024
    max_rows: int = 50000
    demo_enabled: bool = True

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.agent_mode not in {"auto", "ollama", "deterministic"}:
            raise ValueError("agent_mode must be auto, ollama or deterministic")
        if not 4 <= self.max_agent_steps <= 20:
            raise ValueError("max_agent_steps must be between 4 and 20")
        if self.admin_password and len(self.admin_password) < 12:
            raise ValueError("Admin password must have at least 12 characters")
        if self.environment == "production":
            if not self.secure_cookies or not self.frontend_origin.startswith("https://"):
                raise ValueError("Production requires secure cookies and an HTTPS frontend origin")
            if self.demo_enabled:
                raise ValueError("Disable demo seeding in production")
        return self


@lru_cache
def settings():
    return Settings()
