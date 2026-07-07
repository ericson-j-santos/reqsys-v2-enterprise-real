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
    public_environment: str = Field(default_factory=lambda: get_secret('PUBLIC_ENVIRONMENT', '') or '')
    allow_demo_login: bool = Field(default_factory=lambda: _bool_secret('ALLOW_DEMO_LOGIN', 'true'))
    jwt_secret: str = Field(default_factory=lambda: get_secret('JWT_SECRET', 'trocar-em-producao') or 'trocar-em-producao')
    jwt_algorithm: str = 'HS256'
    jwt_issuer: str = Field(default_factory=lambda: get_secret('JWT_ISSUER', '') or '')
    jwt_audience: str = Field(default_factory=lambda: get_secret('JWT_AUDIENCE', '') or '')
    jwt_exp_minutes: int = Field(default_factory=lambda: int(get_secret('JWT_EXP_MINUTES', '60') or '60'))
    database_url: str = Field(default_factory=lambda: get_secret('DATABASE_URL', 'sqlite:///./reqsys.db') or 'sqlite:///./reqsys.db')
    cors_origins: str = Field(default_factory=lambda: get_secret('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8081,http://localhost:8083,http://localhost:8084,http://reqsys.localtest.me:8081,http://reqsys.localtest.me:8083,http://reqsys-test.localtest.me:8084') or 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8081,http://localhost:8083,http://localhost:8084,http://reqsys.localtest.me:8081,http://reqsys.localtest.me:8083,http://reqsys-test.localtest.me:8084')

    # Observabilidade enterprise (Trilha B)
    otel_enabled: bool = Field(default_factory=lambda: _bool_secret('OTEL_ENABLED', 'false'))
    otel_service_name: str = Field(default_factory=lambda: get_secret('OTEL_SERVICE_NAME', 'reqsys-api') or 'reqsys-api')
    otel_exporter_endpoint: str = Field(default_factory=lambda: get_secret('OTEL_EXPORTER_OTLP_ENDPOINT', '') or '')
    log_format: str = Field(default_factory=lambda: get_secret('LOG_FORMAT', 'text') or 'text')

    # Integração GovBI IA — proxy governado backend
    govbi_base_url: str = Field(default_factory=lambda: get_secret('GOVBI_BASE_URL', 'https://govbi-ia-hom.fly.dev') or 'https://govbi-ia-hom.fly.dev')
    govbi_timeout_seconds: float = Field(default_factory=lambda: float(get_secret('GOVBI_TIMEOUT_SECONDS', '15') or '15'))

    # RAG governado — LlamaIndex-ready com fallback offline auditável
    reqsys_rag_documents_path: str = Field(default_factory=lambda: get_secret('REQSYS_RAG_DOCUMENTS_PATH', '') or '')
    reqsys_rag_vector_store: str = Field(default_factory=lambda: get_secret('REQSYS_RAG_VECTOR_STORE', 'in_memory') or 'in_memory')
    reqsys_rag_require_sources: bool = Field(default_factory=lambda: _bool_secret('REQSYS_RAG_REQUIRE_SOURCES', 'true'))

    # Integração com Redmine Wiki Sync service
    wiki_sync_base_url: str = Field(default_factory=lambda: get_secret('WIKI_SYNC_BASE_URL', '') or '')
    wiki_sync_token: str = Field(default_factory=lambda: get_secret('WIKI_SYNC_TOKEN', '') or '')

    # Verificação de versão no GitHub antes de publicar na Wiki
    github_docs_repo: str = Field(default_factory=lambda: get_secret('GITHUB_DOCS_REPO', '') or '')
    github_docs_base_path: str = Field(default_factory=lambda: get_secret('GITHUB_DOCS_BASE_PATH', 'docs/requisitos') or 'docs/requisitos')

    # Token estático para acesso service-to-service ao cofre (POST /v1/cofre/resolver)
    vault_api_token: str = Field(default_factory=lambda: get_secret('VAULT_API_TOKEN', '') or '')

    # vault-service remoto (extração do cofre, ADR-041) — usado por app.core.secrets.get_secret()
    # como fallback além do keyring local. Lido via os.environ direto dentro de secrets.py
    # (não via `settings`, para evitar ciclo de bootstrap); estes campos existem só para
    # diagnóstico/health-check exibirem se está configurado, sem expor o token.
    cofre_service_base_url: str = Field(default_factory=lambda: get_secret('COFRE_API_URL', '') or '')
    cofre_service_token: str = Field(default_factory=lambda: get_secret('COFRE_SERVICE_TOKEN', '') or '')
    cofre_service_timeout_seconds: float = Field(default_factory=lambda: float(get_secret('COFRE_SERVICE_TIMEOUT_SECONDS', '5') or '5'))

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

    # Gemini IA — free tier; modelo configuravel conforme disponibilidade do AI Studio
    gemini_api_key: str = Field(default_factory=lambda: get_secret('GEMINI_API_KEY', '') or '')
    gemini_model: str = Field(default_factory=lambda: get_secret('GEMINI_MODEL', 'gemini-3.5-flash') or 'gemini-3.5-flash')

    # Groq IA — fallback gratuito (llama-3.3-70b: 30 req/min, 14.400 req/dia)
    groq_api_key: str = Field(default_factory=lambda: get_secret('GROQ_API_KEY', '') or '')
    groq_model: str = Field(default_factory=lambda: get_secret('GROQ_MODEL', 'llama-3.3-70b-versatile') or 'llama-3.3-70b-versatile')

    # Codex Governado — providers opcionais
    codex_ollama_base_url: str = Field(default_factory=lambda: get_secret('CODEX_OLLAMA_BASE_URL', 'http://localhost:11434') or 'http://localhost:11434')
    codex_ollama_model: str = Field(default_factory=lambda: get_secret('CODEX_OLLAMA_MODEL', 'qwen2.5-coder:7b') or 'qwen2.5-coder:7b')
    codex_ollama_gateway_url: str = Field(default_factory=lambda: get_secret('CODEX_OLLAMA_GATEWAY_URL', '') or '')
    codex_ollama_gateway_api_key: str = Field(default_factory=lambda: get_secret('CODEX_OLLAMA_GATEWAY_API_KEY', '') or '')
    codex_ollama_gateway_model: str = Field(default_factory=lambda: get_secret('CODEX_OLLAMA_GATEWAY_MODEL', '') or '')
    codex_ollama_gateway_timeout_seconds: int = Field(default_factory=lambda: int(get_secret('CODEX_OLLAMA_GATEWAY_TIMEOUT_SECONDS', '60') or '60'))
    codex_openai_key: str = Field(default_factory=lambda: get_secret('CODEX_OPENAI_KEY', '') or '')
    codex_openai_model: str = Field(default_factory=lambda: get_secret('CODEX_OPENAI_MODEL', 'gpt-4.1-mini') or 'gpt-4.1-mini')
    codex_claude_key: str = Field(default_factory=lambda: get_secret('CODEX_CLAUDE_KEY', '') or '')
    codex_claude_model: str = Field(default_factory=lambda: get_secret('CODEX_CLAUDE_MODEL', 'claude-3-5-sonnet-latest') or 'claude-3-5-sonnet-latest')
    codex_reqsys_endpoint: str = Field(default_factory=lambda: get_secret('CODEX_REQSYS_ENDPOINT', '') or '')
    codex_reqsys_key: str = Field(default_factory=lambda: get_secret('CODEX_REQSYS_KEY', '') or '')

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
    powerautomate_planner_webhook_url: str = Field(default_factory=lambda: get_secret('POWERAUTOMATE_PLANNER_WEBHOOK_URL', '') or '')
    powerautomate_planner_webhook_key: str = Field(default_factory=lambda: get_secret('POWERAUTOMATE_PLANNER_WEBHOOK_KEY', '') or '')
    teams_notifications_webhook_url: str = Field(default_factory=lambda: get_secret('TEAMS_NOTIFICATIONS_WEBHOOK_URL', '') or '')
    # Object ID do service principal do app registration (AZURE_CLIENT_ID) no tenant,
    # necessario para o app se auto-incluir como membro ao criar um chat 1:1 via Graph API.
    teams_graph_app_service_principal_id: str = Field(
        default_factory=lambda: get_secret('TEAMS_GRAPH_APP_SERVICE_PRINCIPAL_ID', '') or ''
    )
    app_public_url: str = Field(default_factory=lambda: get_secret('APP_PUBLIC_URL', '') or '')
    api_public_url: str = Field(default_factory=lambda: get_secret('API_PUBLIC_URL', '') or '')

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
    def cofre_service_configurado(self) -> bool:
        return bool(self.cofre_service_base_url.strip() and self.cofre_service_token.strip())

    @property
    def azure_configured(self) -> bool:
        return bool(self.azure_tenant_id.strip() and self.azure_client_id.strip())

    @property
    def azure_missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.azure_tenant_id.strip():
            missing.append('AZURE_TENANT_ID')
        if not self.azure_client_id.strip():
            missing.append('AZURE_CLIENT_ID')
        return missing

    @property
    def teams_graph_configurado(self) -> bool:
        return self.azure_configured and bool(self.azure_client_secret.strip())

    @property
    def teams_graph_missing_fields(self) -> list[str]:
        missing = list(self.azure_missing_fields)
        if not self.azure_client_secret.strip():
            missing.append('AZURE_CLIENT_SECRET')
        return missing

    @property
    def teams_graph_chat_criacao_configurada(self) -> bool:
        # Criacao de chat 1:1 app-only exige 2 usuarios reais como membros (o
        # service principal do app nao pode ser membro — validado ao vivo em
        # 2026-07-07), entao so depende das credenciais Graph basicas.
        return self.teams_graph_configurado

    @property
    def azure_expected_redirect_uri(self) -> str:
        frontend_origin = (self.app_public_url or self.ambiente_atual_info.get('frontend', '')).rstrip('/')
        return f'{frontend_origin}/auth/callback.html' if frontend_origin else ''

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
        if self.jwt_exp_minutes <= 0:
            errors.append('JWT_EXP_MINUTES deve ser maior que 0 em produção')
        if any(origin == '*' for origin in cors_origins):
            errors.append('CORS_ORIGINS não pode conter * em produção')
        if not self.jwt_issuer.strip():
            errors.append('JWT_ISSUER é obrigatório em produção')
        if not self.jwt_audience.strip():
            errors.append('JWT_AUDIENCE é obrigatório em produção')
        if self.allow_demo_login:
            errors.append('ALLOW_DEMO_LOGIN deve ser false em produção')
        if not self.azure_configured:
            errors.append('Azure AD obrigatório em produção: configure AZURE_TENANT_ID e AZURE_CLIENT_ID')

        from app.services.external_sources_registry import validar_registry_producao

        try:
            validar_registry_producao()
        except RuntimeError as exc:
            errors.append(str(exc))

        if errors:
            raise RuntimeError('Configuração insegura para produção: ' + '; '.join(errors))

    @property
    def normalized_environment(self) -> str:
        value = (self.app_environment or '').strip().lower().replace('-', '_')
        return self._normalize_environment_name(value)

    @property
    def normalized_public_environment(self) -> str:
        value = (self.public_environment or self.app_environment or '').strip().lower().replace('-', '_')
        return self._normalize_environment_name(value)

    @staticmethod
    def _normalize_environment_name(value: str) -> str:
        aliases = {
            'dev': 'desenvolvimento', 'development': 'desenvolvimento', 'local': 'desenvolvimento',
            'test': 'testes', 'teste': 'testes', 'testing': 'testes',
            'stg': 'homologacao', 'staging': 'homologacao', 'homolog': 'homologacao', 'hml': 'homologacao',
            'prod': 'producao', 'production': 'producao',
        }
        return aliases.get(value, value or 'desenvolvimento')

    @property
    def ambientes_urls(self) -> dict[str, dict[str, str]]:
        return {
            'desenvolvimento': {
                'frontend': 'https://reqsys-app-dev.fly.dev', 'api': 'https://reqsys-api-dev.fly.dev/docs',
                'notas': 'Fly dev; local usa docker-compose.yml + docker-compose.dev.yml',
            },
            'producao': {
                'frontend': 'https://reqsys-app.fly.dev', 'api': 'https://reqsys-api.fly.dev/docs',
                'notas': 'Fly producao; local usa docker-compose.yml + docker-compose.prod.yml',
            },
            'testes': {'frontend': 'http://localhost:8084', 'api': 'http://localhost:8212/docs', 'notas': 'Docker test'},
            'homologacao': {'frontend': 'https://reqsys-app-stg.fly.dev', 'api': 'https://reqsys-api-stg.fly.dev', 'notas': 'Fly staging'},
        }

    @property
    def ambiente_atual_info(self) -> dict[str, str]:
        ambiente = self.normalized_environment
        info = dict(self.ambientes_urls.get(ambiente, self.ambientes_urls['desenvolvimento']))
        if self.app_public_url:
            info['frontend'] = self.app_public_url
        if self.api_public_url:
            info['api'] = self.api_public_url
        return info


settings = Settings()
