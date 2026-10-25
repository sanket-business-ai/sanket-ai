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
    llm_provider: str = "ollama"
    # Document embeddings always come from the local Ollama; an empty value turns semantic search off.
    embedding_model: str = "bge-m3"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    # Hosted OpenAI-compatible provider (Groq, Gemini, OpenRouter). Prompts include business data.
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_reasoning_effort: str = ""
    llm_strict_schema: bool = True
    # Free tiers cap tokens per request; Groq counts about 3.2 encoded characters per token, so 18,000
    # characters stays under its 8,000-token limit.
    llm_max_prompt_chars: int = 18000
    # Comma-separated models on the same provider, tried in order when the previous one is rate-limited or down.
    llm_fallback_models: str = ""
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
        if self.llm_provider not in {"ollama", "openai"}:
            raise ValueError("llm_provider must be ollama or openai")
        if self.llm_provider == "openai" and self.agent_mode != "deterministic":
            if not (self.llm_base_url and self.llm_api_key and self.llm_model):
                raise ValueError("The openai provider needs llm_base_url, llm_api_key and llm_model")
            if not self.llm_base_url.startswith("https://"):
                raise ValueError("llm_base_url must use HTTPS")
        # 0 skips model planning: the tools run deterministically and the model only writes the conclusion.
        if not 0 <= self.max_agent_steps <= 20:
            raise ValueError("max_agent_steps must be between 0 and 20")
        if self.admin_password and len(self.admin_password) < 12:
            raise ValueError("Admin password must have at least 12 characters")
        if self.environment == "production":
            if not self.secure_cookies or not self.frontend_origin.startswith("https://"):
                raise ValueError("Production requires secure cookies and an HTTPS frontend origin")
            if self.demo_enabled:
                raise ValueError("Disable demo seeding in production")
        return self

    @property
    def llm_models(self):
        extra = [model.strip() for model in self.llm_fallback_models.split(",") if model.strip()]
        return list(dict.fromkeys([self.llm_model, *extra]))

    @property
    def model_name(self):
        return self.llm_model if self.llm_provider == "openai" else self.ollama_model


@lru_cache
def settings():
    return Settings()
