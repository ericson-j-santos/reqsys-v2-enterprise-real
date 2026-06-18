from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

from app.core.secrets import get_secret

# Carrega o .env do diretório pai (raiz do projeto) se existir
_env_file = Path(__file__).resolve().parents[3] / '.env'

_TRUE_VALUES = {'1', 'true', 'yes', 'on'}
_PRODUCTION_ENVIRONMENTS = {'prod', 'prd', 'production'}
_WEAK_SECRETS = {
    'trocar-em-producao',
    'secret',
    'changeme',
    'TROQUE-POR-UM-SEGREDO-FORTE-MINIMO-32-CHARS',
    '',
}


def _bool_secret(name: str, default: str = 'false') -> bool:
    return (get_secret(name, default) or default).strip().lower() in _TRUE_VALUES


class Settings(BaseSettings):
    model_config = {'env_file': str(_env_file), 'env_file_encoding': 'utf-8', 'extra': 'ignore'}

    app_name: str = 'ReqSys API'
    app_version: str = '3.1.0'
    app_environment: str = Field(default_factory=lambda: get_secret('APP_ENV', get_secret('ENVIRONMENT', 'development') or 'development') or 'development')
    allow_demo_login: bool = Field(default_factory=lambda: _bool_secret('ALLOW_DEMO_LOGIN', 'true'))
    jwt_secret: str = Field(default_factory=lambda: get_secret('JWT_SECRET', 'trocar-em-producao') or 'trocar-em-producao')
    jwt_algorithm: str = 'HS256'
    jwt_issuer: str = Field(default_factory=lambda: get_secret('JWT_ISSUER', '') or '')
    jwt_audience: str = Field(default_factory=lambda: get_secret('JWT_AUDIENCE', '') or '')
    jwt_exp_minutes: int = Field(default_factory=lambda: int(get_secret('JWT_EXP_MINUTES', '60') or '60'))
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

    # Integracao Figma <-> GitHub
    figma_access_token: str = Field(default_factory=lambda: get_secret('FIGMA_ACCESS_TOKEN', '') or '')
    figma_webhook_secret: str = Field(default_factory=lambda: get_secret('FIGMA_WEBHOOK_SECRET', '') or '')
    figma_default_file_key: str = Field(default_factory=lambda: get_secret('FIGMA_DEFAULT_FILE_KEY', '') or '')
    figma_github_default_repo: str = Field(default_factory=lambda: get_secret('FIGMA_GITHUB_DEFAULT_REPO', '') or '')
    enable_figma_github_sync: bool = Field(default_factory=lambda: _bool_secret('ENABLE_FIGMA_GITHUB_SYNC', 'true'))

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
    azure_client_secret: str = Field(default_factory=lambda: get_secret('AZURE_CLIENT_SECRET', '') or '')

    # Hub Low-Code & IA
    sharepoint_site_id: str = Field(default_factory=lambda: get_secret('SHAREPOINT_SITE_ID', '') or '')
    sharepoint_list_ia: str = Field(default_factory=lambda: get_secret('SHAREPOINT_LIST_IA', 'IA_Catalogo_Projetos') or 'IA_Catalogo_Projetos')
    github_pat: str = Field(default_factory=lambda: get_secret('GITHUB_PAT', '') or '')
    github_alm_repo: str = Field(default_factory=lambda: get_secret('GITHUB_ALM_REPO', 'ericson-j-santos/reqsys-powerplatform-alm') or 'ericson-j-santos/reqsys-powerplatform-alm')
    powerautomate_env_id: str = Field(default_factory=lambda: get_secret('POWERAUTOMATE_ENV_ID', '') or '')
    powerautomate_flow_id: str = Field(default_factory=lambda: get_secret('POWERAUTOMATE_FLOW_ID', '73bd346b-c765-f111-ab0c-7ced8da7c8da') or '73bd346b-c765-f111-ab0c-7ced8da7c8da')

    # Copilot Studio / Dataverse provisioning
    copilotstudio_environment_url: str = Field(default_factory=lambda: get_secret('COPILOTSTUDIO_ENVIRONMENT_URL', '') or '')
    copilotstudio_provisioning_webhook_url: str = Field(default_factory=lambda: get_secret('COPILOTSTUDIO_PROVISIONING_WEBHOOK_URL', '') or '')
    copilotstudio_provisioning_webhook_key: str = Field(default_factory=lambda: get_secret('COPILOTSTUDIO_PROVISIONING_WEBHOOK_KEY', '') or '')

    @property
    def is_production(self) -> bool:
        return self.app_environment.strip().lower() in _PRODUCTION_ENVIRONMENTS

    @property
    def is_jwt_secret_weak(self) -> bool:
        secret = (self.jwt_secret or '').strip()
        return secret in _WEAK_SECRETS or len(secret) < 32

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(',') if origin.strip()]

    def validate_production_gates(self) -> None:
        """Bloqueia boot em produção quando a configuração viola gates mínimos."""
        if not self.is_production:
            return

        errors: list[str] = []
        cors_origins = self.cors_origins_list

        if self.is_jwt_secret_weak:
            errors.append('JWT_SECRET fraco, ausente ou padrão')
        if any(origin == '*' for origin in cors_origins):
            errors.append('CORS_ORIGINS não pode conter * em produção')
        if not self.jwt_issuer.strip():
            errors.append('JWT_ISSUER é obrigatório em produção')
        if not self.jwt_audience.strip():
            errors.append('JWT_AUDIENCE é obrigatório em produção')
        if self.allow_demo_login:
            errors.append('ALLOW_DEMO_LOGIN deve ser false em produção')

        if errors:
            raise RuntimeError('Configuração insegura para produção: ' + '; '.join(errors))


settings = Settings()
