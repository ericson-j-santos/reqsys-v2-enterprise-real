# Environment Observability API

Serviço independente e reutilizável para padronizar identificação de ambiente, health checks e logs estruturados em aplicações ReqSys ou externas.

## Contrato HTTP

- `GET /health`
- `GET /api/runtime/health`
- `GET /api/runtime/readiness`
- `GET /api/runtime/liveness`
- `GET /api/v1/environment`
- OpenAPI: `/docs` e `/openapi.json`

## Reutilização

A integração é feita por HTTP, sem acoplamento ao domínio do ReqSys. Cada aplicação consumidora pode consultar `/api/v1/environment`, propagar `x-correlation-id` e usar os health checks em Kubernetes, Fly.io, Docker Compose, Power Platform custom connectors ou gateways internos.

## Logs

Saída JSON em `stdout`, com ambiente, serviço, versão, commit, `correlation_id`, `causation_id`, `workflow_run_id`, request ID, trace context, rota, status e duração. Os headers opcionais `X-Causation-Id` e `X-Workflow-Run-Id` são aceitos apenas em formato seguro e são propagados na resposta quando válidos. Senhas, tokens, cookies, connection strings e payloads pessoais não são registrados.

## Execução local

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest -q
```

## Publicação segregada

O antigo procedimento Fly.io foi retirado permanentemente em 2026-10-02. A
publicação deve usar o provedor corporativo vigente, com endpoint HTTPS
explícito e segregação de secrets, domínios e telemetria por ambiente. Não há
manifesto nem comando de deploy Fly suportado neste serviço.

## Variáveis

| Variável | Finalidade | Padrão |
|---|---|---|
| `APP_ENV` | Ambiente explícito | `development` |
| `SERVICE_NAME` | Nome lógico | `environment-observability-api` |
| `SERVICE_VERSION` | Versão | `0.1.0` |
| `GITHUB_SHA` | Commit implantado | `unknown` |
| `LOG_LEVEL` | Nível mínimo | `INFO` |
| `READINESS_ENABLED` | Controle de prontidão | `true` |
