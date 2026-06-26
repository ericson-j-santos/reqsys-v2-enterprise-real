# ReqSys Fly Runtime P0

## Objetivo

Versionar a publicação mínima da API ReqSys no Fly para expor, com segurança e evidência, os endpoints públicos de smoke, health e observabilidade runtime.

## Escopo P0

Endpoints esperados após deploy:

```http
GET /
GET /health
GET /api/runtime/health
GET /api/runtime/readiness
GET /api/runtime/liveness
GET /api/runtime/metrics
GET /api/runtime/dashboard
```

## Escopo P1 opcional

Após P0 verde, validar Agile Runtime em modo leitura:

```http
GET /v1/agile-runtime/resumo
GET /v1/agile-runtime/sprints
GET /v1/agile-runtime/work-items
```

Rotas de escrita do Agile Runtime devem ser liberadas somente após validação de banco, autenticação, auditoria e RBAC.

## Arquivos versionados

- `fly.toml`
- `Dockerfile.fly`
- `.github/workflows/fly-runtime-p0.yml`
- `scripts/validate_fly_runtime_config.py`
- `scripts/validate_public_runtime.py`

## Secrets obrigatórios no Fly

A aplicação bloqueia boot inseguro em produção. Configure os valores reais no Fly, nunca no Git.

```bash
fly secrets set \
  JWT_SECRET="<segredo-forte-com-32-ou-mais-caracteres>" \
  JWT_ISSUER="reqsys-api" \
  JWT_AUDIENCE="reqsys-users" \
  AZURE_TENANT_ID="<tenant-id>" \
  AZURE_CLIENT_ID="<client-id>" \
  --app reqsys-api
```

Secrets opcionais, conforme integrações habilitadas:

```bash
fly secrets set \
  AZURE_CLIENT_SECRET="<client-secret>" \
  GITHUB_WEBHOOK_SECRET="<webhook-secret>" \
  GITLAB_WEBHOOK_TOKEN="<gitlab-token>" \
  --app reqsys-api
```

## Volume persistente

O `fly.toml` usa SQLite persistido em `/data/reqsys.db`. Antes do primeiro deploy, criar volume:

```bash
fly volumes create reqsys_data --region gru --size 1 --app reqsys-api
```

## Validação local da configuração

```bash
python scripts/validate_fly_runtime_config.py
```

## Deploy manual controlado

```bash
fly deploy --config fly.toml --remote-only --app reqsys-api
```

## Validação pública pós-deploy

```bash
python scripts/validate_public_runtime.py \
  --base-url https://reqsys-api.fly.dev \
  --output public-runtime-validation.json
```

## Workflow GitHub Actions

Workflow: `ReqSys Fly Runtime P0`

Modos:

1. **Pull request**: valida arquivos, gates mínimos e build Docker.
2. **workflow_dispatch com `deploy=false`**: valida URL pública e gera artifact de evidência.
3. **workflow_dispatch com `deploy=true`**: executa deploy no Fly e valida URL pública se o deploy passar.

Secret necessário no GitHub para deploy via Actions:

```text
FLY_API_TOKEN
```

## Gates obrigatórios

- Sem `JWT_SECRET` versionado.
- Sem `AZURE_CLIENT_SECRET` versionado.
- Sem wildcard em `CORS_ORIGINS`.
- `ALLOW_DEMO_LOGIN=false` em produção.
- `force_https=true` no Fly.
- Health check em `/health`.
- Deploy somente com secret `FLY_API_TOKEN` configurado.

## Critério de pronto

| Critério | Estado esperado |
|---|---|
| Configuração versionada | Verde |
| Docker build smoke | Verde |
| Deploy Fly | Verde |
| `/` | HTTP 2xx |
| `/health` | HTTP 2xx |
| `/api/runtime/health` | HTTP 2xx |
| `/api/runtime/readiness` | HTTP 2xx |
| `/api/runtime/liveness` | HTTP 2xx |
| `/api/runtime/metrics` | HTTP 2xx |
| `/api/runtime/dashboard` | HTTP 2xx |
| Artifact `public-runtime-validation.json` | Publicado |

## Limites

- Este incremento não cria secrets.
- Este incremento não faz bypass de environment approval.
- Este incremento não libera rotas de escrita do Agile Runtime como produção consolidada.
- Este incremento não promove PRs em draft para produção.
