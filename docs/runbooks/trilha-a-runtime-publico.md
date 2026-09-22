# Trilha A — Runtime Público

## Objetivo

Estabilizar o runtime público Fly.io com validação versionada, boot resiliente, healthcheck em camadas, fallback de evidência e validador consolidado — evoluindo de forma isolada das demais trilhas.

## Componentes

| Componente | Arquivo | Função |
| --- | --- | --- |
| Boot resiliente | `scripts/fly_boot.sh` | Aguarda volume `/data` gravável; fallback opcional para SQLite efêmero |
| Healthcheck container | `Dockerfile.fly` | `HEALTHCHECK` em `/health` com `start-period=30s` |
| Healthcheck Fly | `fly.toml` | `[[http_service.checks]]` em `/health`, `grace_period=30s` |
| Probe DB startup | `backend/app/core/runtime_boot.py` | Retries no startup e em `/health` |
| Validador consolidado | `scripts/runtime_public_validator.py` | Config + Docker + probe opcional + fallback |
| Smoke público | `scripts/validate_public_runtime.py` | Probe HTTP read-only (reutilizado pelo validador) |
| CI | `.github/workflows/fly-runtime-p0.yml` | Gate em PR e smoke manual |

## Execução local

### Validar configuração e Docker (sem probe HTTP)

```bash
python scripts/runtime_public_validator.py \
  --artifact-root . \
  --output artifacts/runtime/runtime-public-validation.json
```

### Validar URL pública (probe live)

```bash
python scripts/runtime_public_validator.py \
  --probe \
  --base-url https://reqsys-api.fly.dev \
  --environment prod \
  --include-optional-evidence \
  --output artifacts/runtime/runtime-public-validation.json \
  --strict
```

### Fallback automático

Sem `--probe`, o validador tenta carregar evidência em cache, nesta ordem:

1. `audit/runtime/public-runtime-validation.json`
2. `artifacts/runtime/public-runtime-validation.json`
3. `public-runtime-validation.json`

Quando o probe live falha mas há cache válido, o resumo fica `degraded_with_fallback` com `confidence=medium`.

## Boot resiliente

Variáveis suportadas no container Fly:

| Variável | Default | Descrição |
| --- | --- | --- |
| `REQSYS_DATA_DIR` | `/data` | Diretório do volume persistente |
| `REQSYS_BOOT_MAX_ATTEMPTS` | `30` | Tentativas de escrita antes de abortar |
| `REQSYS_BOOT_FALLBACK` | `false` | Usar SQLite efêmero em `/tmp` se volume indisponível |
| `REQSYS_BOOT_FALLBACK_DATABASE_URL` | `sqlite:////tmp/reqsys-fallback.db` | URL usada no fallback |

Em produção, `REQSYS_BOOT_FALLBACK` deve permanecer `false`.

## Healthcheck em camadas

```text
Fly proxy check (/health, grace 30s)
  → Docker HEALTHCHECK (/health, start-period 30s)
    → FastAPI /health (probe DB 1x)
      → Startup hook (probe DB com retries em produção)
```

`/health` retorna HTTP 503 quando o banco não responde, sinalizando máquina não pronta para tráfego.

## Critérios de pronto (Trilha A)

| Critério | Estado esperado |
| --- | --- |
| `validate_fly_runtime_config.py` | Verde |
| `runtime_public_validator.py` (sem probe) | `operational_status=config_ready` ou melhor |
| Docker build smoke | Verde |
| Probe público strict | 4/4 endpoints canônicos HTTP 2xx |
| Artifact | `runtime-public-validation.json` publicado |
| Boot | Volume `/data` gravável antes do uvicorn |

## Limites

- Não cria secrets Fly nem GitHub.
- Não executa deploy sem `workflow_dispatch` explícito.
- Não relaxa gates JWT/CORS/auth.
- Fallback de banco em `/tmp` é apenas para diagnóstico; não usar em produção.

## Relação com outras trilhas

Esta trilha pode evoluir isolada. Integrações opcionais:

- **Public Runtime Evidence Gate** — alimenta `audit/runtime/` consumido pelo fallback.
- **Runtime Health Validator** — matriz Fly com `--probe-env`.
- **Ops Dashboard** — cards de readiness público.
