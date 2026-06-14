from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

from app.core.secrets import get_secret

# Carrega o .env do diretório pai (raiz do projeto) se existir
_env_file = Path(__file__).resolve().parents[3] / '.env'

class Settings(BaseSettings):
    model_config = {'env_file': str(_env_file), 'env_file_encoding': 'utf-8', 'extra': 'ignore'}

    app_name: str = 'ReqSys API'
    app_version: str = '3.1.0'
    jwt_secret: str = Field(default_factory=lambda: get_secret('JWT_SECRET', 'trocar-em-producao') or 'trocar-em-producao')
    jwt_algorithm: str = 'HS256'
    database_url: str = Field(default_factory=lambda: get_secret('DATABASE_URL', 'sqlite:///./reqsys.db') or 'sqlite:///./reqsys.db')
    cors_origins: str = Field(default_factory=lambda: get_secret('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8081,http://localhost:8083,http://localhost:8084,http://reqsys.localtest.me:8081,http://reqsys.localtest.me:8083,http://reqsys-test.localtest.me:8084') or 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8081,http://localhost:8083,http://localhost:8084,http://reqsys.localtest.me:8081,http://reqsys.localtest.me:8083,http://reqsys-test.localtest.me:8084')

    # Integração com Redmine Wiki Sync service
    wiki_sync_base_url: str = Field(default_factory=lambda: get_secret('WIKI_SYNC_BASE_URL', '') or '')
    wiki_sync_token: str = Field(default_factory=lambda: get_secret('WIKI_SYNC_TOKEN', '') or '')

    # Verificação de versão no GitHub antes de publicar na Wiki
    github_docs_repo: str = Field(default_factory=lambda: get_secret('GITHUB_DOCS_REPO', '') or '')
    github_docs_base_path: str = Field(default_factory=lambda: get_secret('GITHUB_DOCS_BASE_PATH', 'docs/requisitos') or 'docs/requisitos')

    # Token estático para acesso service-to-service ao cofre (POST /v1/cofre/resolver)
    vault_api_token: str = Field(default_factory=lambda: get_secret('VAULT_API_TOKEN', '') or '')

    # Git webhooks — rastreabilidade
    github_webhook_secret: str = Field(default_factory=lambda: get_secret('GITHUB_WEBHOOK_SECRET', '') or '')
    gitlab_webhook_token: str = Field(default_factory=lambda: get_secret('GITLAB_WEBHOOK_TOKEN', '') or '')

    # Caminho para o .sdd do my-first-spec-project (absoluto ou relativo ao reqsys root)
    sdd_specs_path: str = Field(default_factory=lambda: get_secret('SDD_SPECS_PATH', '') or '')

    # Gemini IA — free tier (gemini-2.0-flash: 15 req/min, 1500 req/dia)
    gemini_api_key: str = Field(default_factory=lambda: get_secret('GEMINI_API_KEY', '') or '')
    gemini_model: str = Field(default_factory=lambda: get_secret('GEMINI_MODEL', 'gemini-2.0-flash') or 'gemini-2.0-flash')

    # Groq IA — fallback gratuito (llama-3.3-70b: 30 req/min, 14.400 req/dia)
    groq_api_key: str = Field(default_factory=lambda: get_secret('GROQ_API_KEY', '') or '')
    groq_model: str = Field(default_factory=lambda: get_secret('GROQ_MODEL', 'llama-3.3-70b-versatile') or 'llama-3.3-70b-versatile')

    # Azure AD (Microsoft Entra ID) — tenant Tieri659
    azure_tenant_id: str = Field(default_factory=lambda: get_secret('AZURE_TENANT_ID', '') or '')
    azure_client_id: str = Field(default_factory=lambda: get_secret('AZURE_CLIENT_ID', '') or '')

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

settings = Settings()
