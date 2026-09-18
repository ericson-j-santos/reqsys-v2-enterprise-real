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

Saída JSON em `stdout`, com ambiente, serviço, versão, commit, correlation ID, request ID, trace context, rota, status e duração. Senhas, tokens, cookies, connection strings e payloads pessoais não são registrados.

## Execução local

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest -q
```

## Deploy segregado

```bash
fly apps create reqsys-env-api-dev
fly deploy --config fly.dev.toml

fly apps create reqsys-env-api-stg
fly deploy --config fly.stg.toml

fly apps create reqsys-env-api-prod
fly deploy --config fly.prod.toml
```

Os três aplicativos, secrets, domínios e telemetria devem permanecer separados. O pipeline deve promover a mesma imagem imutável de STG para PROD; os arquivos atuais estabelecem o contrato inicial, mas a criação administrativa dos aplicativos e secrets depende de credencial Fly.io autorizada.

## Variáveis

| Variável | Finalidade | Padrão |
|---|---|---|
| `APP_ENV` | Ambiente explícito | `development` |
| `SERVICE_NAME` | Nome lógico | `environment-observability-api` |
| `SERVICE_VERSION` | Versão | `0.1.0` |
| `GITHUB_SHA` | Commit implantado | `unknown` |
| `LOG_LEVEL` | Nível mínimo | `INFO` |
| `READINESS_ENABLED` | Controle de prontidão | `true` |
