from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    env: str
    ollama_base_url: str
    auth_required: bool
    allowed_origins: tuple[str, ...]

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "prod"


def load_settings() -> Settings:
    env = os.getenv("REQSYS_ENV", "dev")
    origins = tuple(
        origin.strip()
        for origin in os.getenv("REQSYS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    )
    settings = Settings(
        env=env,
        ollama_base_url=os.getenv("REQSYS_OLLAMA_BASE_URL", "http://localhost:11434"),
        auth_required=os.getenv("REQSYS_AUTH_REQUIRED", "true").lower() == "true",
        allowed_origins=origins,
    )
    if settings.is_production and not settings.auth_required:
        raise RuntimeError("Auth obrigatoria em producao")
    if settings.is_production and "*" in settings.allowed_origins:
        raise RuntimeError("CORS wildcard bloqueado em producao")
    return settings
