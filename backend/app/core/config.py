import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings

from app.core.secrets import get_secret

# Carrega o .env do diretório pai (raiz do projeto) se existir
_env_file = Path(__file__).resolve().parents[3] / '.env'

class Settings(BaseSettings):
    model_config = {'env_file': str(_env_file), 'env_file_encoding': 'utf-8', 'extra': 'ignore'}

    app_name: str = 'ReqSys API'
    jwt_secret: str = Field(default_factory=lambda: get_secret('JWT_SECRET', 'trocar-em-producao') or 'trocar-em-producao')
    jwt_algorithm: str = 'HS256'
    database_url: str = Field(default_factory=lambda: get_secret('DATABASE_URL', 'sqlite:///./reqsys.db') or 'sqlite:///./reqsys.db')
    cors_origins: str = Field(default_factory=lambda: get_secret('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8082,http://reqsys.localtest.me:8082') or 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8082,http://reqsys.localtest.me:8082')

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

settings = Settings()
