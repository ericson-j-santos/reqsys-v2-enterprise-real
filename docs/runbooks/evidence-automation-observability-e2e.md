# Evidence Automation Observability E2E

## Objetivo

Completar a cadeia de evidência pública após o **Public Runtime Evidence Gate** strict verde, validando observabilidade runtime (métricas, dashboard, analytics, página `/runtime` e propagação de `correlation_id`).

Este incremento é o **#2** da trilha de evidência pública:

```text
fly-runtime-p0-deploy
  → Public Runtime Evidence Gate (strict)
    → evidence-automation-observability-e2e  ← este incremento
```

## Bloqueio conhecido

Enquanto `/health` responder 200 e `/api/runtime/*` retornar 404 no Fly, o precondition strict falha com nota `fly_runtime_deploy_lag`. Corrigir via **ReqSys Fly Runtime P0** (`deploy=true`) antes de declarar este gate verde em produção.

## Workflow

```text
.github/workflows/evidence-automation-observability-e2e.yml
```

## Quando executa

1. **Automático**: após `Public Runtime Evidence Gate` concluir com `success` em `main`.
2. **Manual**: `workflow_dispatch` para diagnóstico ou revalidação.

## Scripts

| Script | Função |
|---|---|
| `scripts/validate_observability_e2e.py` | Probe read-only de observabilidade |
| `scripts/persist_observability_e2e_evidence.py` | Persistência em `audit/runtime/` |

## Checks validados

| Check | Endpoint | Critério |
|---|---|---|
| `strict_precondition` | `/health`, `/api/runtime/health\|readiness\|liveness` | HTTP 2xx (bloqueia se deploy lag) |
| `metrics_text_plain` | `/api/runtime/metrics` | `text/plain` com métricas `reqsys_*` |
| `dashboard_schema` | `/api/runtime/dashboard` | JSON com `observability_readiness`, `correlation_id`, `cards` |
| `analytics_telemetry` | `/api/runtime/analytics` | JSON com `operational_telemetry.correlation_id` |
| `runtime_page` | `/runtime` | HTML com marcador operacional |
| `correlation_propagation` | `/api/runtime/health` | `X-Correlation-ID` no header e `meta.correlation_id` |

## Execução manual

```bash
gh workflow run "Evidence Automation Observability E2E" \
  -f public_url="https://reqsys-api.fly.dev" \
  -f strict=true \
  -f skip_precondition=false
```

### Validação local (wire, sem rede)

```bash
python3 scripts/validate_observability_e2e.py \
  --base-url http://127.0.0.1:8000 \
  --skip-precondition \
  --output /tmp/observability-e2e-validation.json
```

## Artefatos publicados

| Artefato | Caminho |
|---|---|
| Validação | `audit/runtime/observability-e2e-validation.json` |
| Índice | `audit/runtime/observability-e2e-evidence-index.json` |
| Resumo | `audit/runtime/observability-e2e-evidence.md` |
| GitHub artifact | `observability-e2e-evidence` |

## Critério de pronto

| Critério | Estado esperado |
|---|---|
| Precondition strict | Verde (pós fly-runtime-p0-deploy) |
| Observability checks | 5/5 verdes |
| `gate_passed` | `true` |
| Workflow | `success` com `strict=true` |
| Nota `fly_runtime_deploy_lag` | Ausente no índice observability E2E |

## Limites

- Não executa deploy Fly.
- Não cria ou altera secrets.
- Não substitui E2E de login Microsoft.
- `skip_precondition=true` é somente para wire/diagnóstico local — não declarar produção healthy com esse modo.

## Relação com outros gates

| Gate upstream | Gate downstream |
|---|---|
| `ReqSys Fly Runtime P0` | Publica runtime no Fly |
| `Public Runtime Evidence Gate` | Strict 4/4 endpoints |
| **Este incremento** | Observabilidade E2E 5/5 checks |
| `CI Observability` | Duração/flaky de workflows CI (escopo distinto) |
