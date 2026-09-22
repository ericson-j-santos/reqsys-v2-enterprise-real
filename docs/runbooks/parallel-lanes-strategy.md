# Estratégia de Paralelização Segura — ReqSys

## Objetivo

Aumentar throughput de entrega com PRs paralelos **somente** em domínios desacoplados, reduzindo rebase manual, `mergeable=false` e instabilidade de CI.

## Estado de referência

- **Baseline:** PR #504 — governança OpenAPI P0 (`openapi-contract-governance.yml`, validador Python, contrato v0.3.0).
- **Índice machine-readable:** `artifacts/parallel-pr-governance/safe-lanes.json`.

## Lanes de execução

| Lane | Domínio | Risco de conflito | Escopo |
| --- | --- | --- | --- |
| **A** — OpenAPI Evolution | `contracts/openapi/`, workflows `openapi-*` | Baixo | Spectral lint, diff semântico AST (advisory), Postman gerado, Newman CI |
| **B** — Docs Runtime Governance | `docs/audit/`, `docs/dashboard/`, `docs/ops-dashboard/data/` | Muito baixo | Artifacts JSON na docs, status navegável, cards executivos, links evidenciáveis |
| **C** — Contract Sync | `scripts/validate_openapi_routes_drift.py` | Médio/baixo | Validação backend routes ↔ OpenAPI via `app.openapi()`, drift automático, **gate strict bloqueante** |
| **D** — Observabilidade Operacional | `docs/ops-dashboard/data/merge-*` | Baixo | Prioridade de lanes, semáforo operacional, índices executivos |

## Mapeamento path → lane

| Prefixo | Lane | Paralelismo |
| --- | --- | --- |
| `docs/*` (exceto contrato OpenAPI compartilhado) | B | até 3 PRs |
| `ci/*` / `.github/workflows/openapi-*` | A | até 2 PRs (workflows dedicados) |
| `ops/*` / `docs/ops-dashboard/` | D | até 2 PRs |
| `contracts/*` (schemas OpenAPI auxiliares) | A | até 2 PRs |
| `runtime/*` / `backend/` | — | **bloqueado** em paralelo |
| `frontend/*` | — | **bloqueado** em paralelo |

## Regras operacionais

Abrir PR paralelo **somente** quando:

1. Não tocar os mesmos arquivos de outro PR aberto.
2. Não alterar os mesmos workflows (workflows globais = serial).
3. Não compartilhar contratos mutáveis (`docs-site/assets/openapi/*.json` = uma PR por vez).
4. Não partir de branch com CI instável.

## O que NÃO paralelizar

- Fly runtime + workflows globais simultaneamente.
- Múltiplos PRs em `.github/workflows/ci.yml` ou mesh/orchestrator.
- Alterações concorrentes em `mkdocs.yml`.
- Múltiplos PRs no mesmo dashboard HTML (`operational-evidence-hub.html` = 1 PR).
- Múltiplos PRs no governance core (`coordenador_status_consolidator.py`, `agent_increment_gate.py`).

## Workflows por lane

| Workflow | Lane | Modo |
| --- | --- | --- |
| `openapi-contract-governance.yml` | A (P0 #504) | blocking |
| `openapi-spectral-lint.yml` | A | report-only |
| `openapi-newman-ci.yml` | A | smoke (localhost) |
| `openapi-semantic-diff.yml` | A (P2) | report-only (advisory AST) |
| `openapi-routes-drift.yml` | C | **blocking strict** (`--strict`) |

## Gate bloqueante canônico (decisão de produto)

| Papel | Script / workflow | Modo |
| --- | --- | --- |
| **Canônico — bloqueia merge** | `validate_openapi_routes_drift.py` + job `routes-drift-strict` | `--strict` quando drift > 0 |
| **Advisory — não bloqueia** | `openapi_semantic_diff.py` + `openapi-semantic-diff.yml` | diff AST estático; útil para diagnóstico precoce |
| **Agent increment gate** | `agent_increment_gate.py --strict` | lê `openapi-routes-drift.json` (canônico), não semantic diff |

O semantic diff AST (Lane A P2) permanece para sinalização precoce sem subir o backend; o gate de merge e o `--strict` do agente usam somente routes-drift (introspecção runtime via FastAPI).

## Evidências e dashboards

- Artifact validação: `artifacts/openapi/openapi-contract-validation.json`
- Snapshot docs: `docs/audit/openapi/openapi-contract-validation.json`
- Índice executivo: `docs/ops-dashboard/data/openapi-governance-index.json`
- Hub: `docs/dashboard/operational-evidence-hub.html` (seção OpenAPI Governance)
- Drift routes (canônico): `artifacts/openapi/openapi-routes-drift.json`
- Diff semântico AST (advisory): `artifacts/openapi/openapi-semantic-diff.json`

## Critério de pausa

Pausar abertura de novos PRs paralelos quando:

- PR ficar atrás da `main` e tocar arquivo concorrente;
- checks obrigatórios instáveis;
- mesmo domínio já tiver PR aberto;
- `coordenador-status.json` com `new_front_allowed: false` (usar `gap_fix` / `consolidate`).

## Resultado esperado

- Maior throughput sem conflito estrutural.
- Menos rebase manual.
- Menor taxa de `mergeable=false`.
- CI mais estável por isolamento de path filters.
- Menor gargalo operacional no coordenador.

## Referências

- Fila paralela: `docs/runbooks/parallel-pr-queue.md`
- Contrato OpenAPI: `docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json`
- API docs: `docs-site/api/openapi.md`
