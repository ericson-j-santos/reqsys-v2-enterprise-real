# Operational Command Center — ReqSys

## Objetivo

Centralizar a navegacao operacional do ReqSys em torno do dashboard dinamico, artifacts, workflows, contratos e runbooks.

## Entrada principal

- `docs/dashboard/live-operational-dashboard.dynamic.html`

## Artifacts consumidos

| Artifact | Origem | Uso |
|---|---|---|
| `ci-lead-time-analytics.json` | CI Lead Time Analytics | lead time, P50, P95, gargalos |
| `operational-history-snapshot.json` | Operational History Snapshot | baseline e historico |
| `runtime-predictive-analytics.json` | Runtime Predictive Analytics | risco preditivo e recomendacoes |
| `operational-maturity-score.json` | Operational Maturity Score | maturidade, gaps e dimensoes |
| `operational-artifact-discovery-index.json` | Operational Artifact Discovery Index | catalogo de artifacts |
| `golden-release-readiness.json` | Golden Release Readiness | prontidao operacional |

## Runbooks relacionados

| Runbook | Finalidade |
|---|---|
| `docs/runbooks/ci-lead-time-analytics.md` | lead time e gargalos |
| `docs/runbooks/operational-history-snapshots.md` | historico operacional |
| `docs/runbooks/runtime-predictive-analytics.md` | analytics preditivo |
| `docs/runbooks/operational-artifact-discovery-index.md` | descoberta de artifacts |
| `docs/runbooks/post-merge-operational-maturity-matrix.md` | maturidade pos-merge |
| `docs/runbooks/golden-release-operational-checklist.md` | checklist operacional |

## Estado atual estimado

| Dimensao | Atual | Alvo | Gap |
|---|---:|---:|---:|
| Command center navegavel | 90% | 98% | 8 p.p. |
| Artifacts integrados ao dashboard | 95% | 98% | 3 p.p. |
| Contratos versionados | 98% | 99% | 1 p.p. |
| Readiness report-only | 98% | 99% | 1 p.p. |

## Regras operacionais

- O dashboard e visualizacao executiva e nao substitui CI obrigatorio.
- Artifacts report-only devem ser tratados como evidencia operacional.
- Mudancas sensiveis exigem PR separado e evidencia especifica.
- Rodadas paralelas devem seguir limite padrao de 3 PRs.

## Proximas evolucoes

1. Publicar o command center em ambiente navegavel controlado.
2. Adicionar historico por `run_id` no dashboard.
3. Criar drill-down por artifact e workflow.
