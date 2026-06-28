# Fly Runtime P0 — Evidência Pós-Deploy (Padrão Ouro)

**Data:** 2026-06-28  
**Incremento:** `fly-runtime-p0-deploy`  
**Trilha:** A — Runtime Público  
**Modo:** governado · sem bypass de secrets · sem relaxamento de gates

## Objetivo

Fechar o ciclo operacional após deploy no Fly (`reqsys-api`) com evidência versionada, rastreável e consumível pelo Ops Dashboard, Coordenador e Trilha A.

Resolve o sintoma documentado: `/health` retorna 200 e `/api/runtime/*` retorna 404 (deploy anterior ao Runtime Operational Observability v1).

## Pré-condições

| Item | Estado esperado |
|---|---|
| `main` com endpoints runtime versionados | Merge recente com `backend/app/main.py` + `monitoramento_operacional.py` |
| `python scripts/validate_fly_runtime_config.py` | `ok: true` |
| Secret GitHub `FLY_API_TOKEN` | Configurado |
| Secrets Fly (`JWT_SECRET`, `JWT_ISSUER`, `JWT_AUDIENCE`, Azure AD) | Configurados no app |
| Volume `reqsys_data` em `gru` | Existente |
| Semáforo coordenador | Preferencialmente verde ou amarelo sem `OPS-GAP-*` crítico |

## Disparo governado (escolha um)

### Opção A — Workflow canônico Fly P0

```text
Workflow: ReqSys Fly Runtime P0
Inputs:
  public_url = https://reqsys-api.fly.dev
  deploy     = true
Environment: production (aprovação humana se exigida)
```

### Opção B — Padrão Ouro Delivery Automation

```text
Workflow: Padrão Ouro Delivery Automation
Input: action = deploy_runtime_only
```

Executa: `validate-runtime` → `deploy-fly-prod` → `public-runtime-smoke` com probe strict em `/api/runtime/*`.

### Opção C — CLI local (operador com token)

```bash
flyctl deploy --remote-only --config fly.toml --app reqsys-api
```

Use somente quando Actions indisponível; publicar evidência manualmente (passo 2).

## Passo 1 — Deploy

Aguardar conclusão sem erro. Rollback: redeploy do SHA anterior estável via Fly releases.

## Passo 2 — Coletar evidência strict

```bash
python scripts/runtime_public_validator.py \
  --probe \
  --base-url https://reqsys-api.fly.dev \
  --environment prod \
  --include-optional-evidence \
  --artifact-root . \
  --output artifacts/runtime/runtime-public-probe.json \
  --strict
```

Endpoints **obrigatórios** (strict):

```http
GET /health
GET /api/runtime/health
GET /api/runtime/readiness
GET /api/runtime/liveness
```

Endpoints **opcionais** (não bloqueiam strict, mas registram maturidade):

```http
GET /
GET /api/runtime/metrics
GET /api/runtime/dashboard
```

## Passo 3 — Publicar artifacts canônicos

| Destino | Caminho | Consumidor |
|---|---|---|
| Artifact CI | `artifacts/runtime/runtime-public-probe.json` | Workflow Fly P0 / Padrão Ouro |
| Audit runtime | `audit/runtime/public-runtime-validation.json` | Ops Dashboard `health.json` |
| Índice evidência | `audit/runtime/public-runtime-evidence-index.json` | Public Runtime Evidence Gate |

Após probe verde, copiar/sincronizar:

```bash
cp artifacts/runtime/runtime-public-probe.json audit/runtime/public-runtime-validation.json
python scripts/persist_public_runtime_evidence.py  # se disponível no repo
```

## Passo 4 — Validar gates dependentes

| Gate / incremento | Critério |
|---|---|
| `health.json` → `public_runtime_readiness` | `strict_gate_passed: true`, `readiness_percent: 100` |
| Public Runtime Evidence Gate | `success_percentual: 100` nos endpoints strict |
| `evidence-automation-observability-e2e` | Desbloqueado após este incremento |
| Coordenador Status | Reexecutar **Coordenador Status Consolidator** |

## Passo 5 — Smoke manual rápido

```bash
curl -fsS https://reqsys-api.fly.dev/api/runtime/health | head -c 200
curl -fsS https://reqsys-api.fly.dev/api/runtime/readiness | head -c 200
curl -fsS https://reqsys-api.fly.dev/api/runtime/liveness | head -c 200
```

Referência: [`public-runtime-smoke-test.md`](public-runtime-smoke-test.md)

## Critério de pronto (Padrão Ouro)

| Critério | Estado |
|---|---|
| Deploy Fly | `success` |
| Probe strict 4/4 | HTTP 2xx |
| Artifact `public-runtime-validation` | Publicado |
| `blocking_issues` sem 404 em `/api/runtime/*` | Vazio |
| Ops Dashboard readiness | `>= 75%` ou `healthy` |
| Nota `fly_runtime_deploy_lag` | Removida ou resolvida |

## Template de evidência (PR / issue)

```text
Semáforo pós-deploy: verde | amarelo | vermelho
SHA deployado: <sha>
Run Actions: <url>
Probe strict: <4/4 ou falhas>
readiness_percent: <valor>
Próximo incremento desbloqueado: evidence-automation-observability-e2e
Correlation ID: <id>
```

## Rollback

1. `flyctl releases list -a reqsys-api`
2. `flyctl releases rollback -a reqsys-api`
3. Reexecutar probe strict — registrar `rollback_required` na evidência
4. Não promover `evidence-automation-observability-e2e` até novo deploy verde

## Limites

- Não cria nem expõe secrets.
- Não habilita `ALLOW_DEMO_LOGIN` em produção.
- Não substitui E2E de login Microsoft.
- Não faz merge de PRs automaticamente.

## Referências Tier 1

- [`fly-runtime-p0.md`](fly-runtime-p0.md) — escopo P0 e arquivos versionados
- [`trilha-a-runtime-publico.md`](trilha-a-runtime-publico.md) — validador consolidado
- [`public-runtime-evidence-gate.md`](public-runtime-evidence-gate.md) — gate read-only recorrente
- [`docs/padrao-ouro/ENGINEERING_PLAYBOOKS.md`](../padrao-ouro/ENGINEERING_PLAYBOOKS.md) — Release governance
- [`docs/padrao-ouro/RUNTIME_EVIDENCE_GRAPH.md`](../padrao-ouro/RUNTIME_EVIDENCE_GRAPH.md) — grafo de evidências
