# Command Center Evidence Index — ReqSys

## Objetivo

Catalogar as evidencias operacionais usadas pelo command center do ReqSys, mantendo rastreabilidade entre artifacts, contratos, dashboard e runbooks.

## Evidencias principais

| Evidencia | Caminho | Consumidor |
|---|---|---|
| Lead time analytics | `audit/ci-lead-time-analytics.json` | Dashboard dinamico |
| Historico operacional | `audit/history/operational-history-snapshot.json` | Dashboard dinamico |
| Risco preditivo | `audit/predictive/runtime-predictive-analytics.json` | Dashboard dinamico |
| Maturidade operacional | `audit/maturity/operational-maturity-score.json` | Dashboard dinamico |
| Descoberta de artifacts | `audit/artifact-discovery/operational-artifact-discovery-index.json` | Dashboard dinamico |
| Readiness de release | `audit/release-readiness/golden-release-readiness.json` | Dashboard dinamico |
| Release Validation Layer | `audit/release-validation/release-validation-layer.json` | Dashboard dinamico + coordenador |
| Readiness do command center | `audit/command-center/command-center-readiness.json` | Dashboard dinamico |
| Validacao de contratos | `audit/extended-contract-validation/extended-operational-contract-validation.json` | Dashboard dinamico |
| Delivery readiness | `audit/delivery-readiness/delivery-readiness-report.json` | Operational Evidence Hub |
| Delivery completion | `audit/delivery-completion/delivery-completion-snapshot.json` | Operational Evidence Hub |
| Delivery finalization | `audit/delivery-finalization/delivery-finalization-report.json` | Operational Evidence Hub |
| Maturity snapshot | `audit/delivery-maturity/delivery-maturity-snapshot.json` | Operational Evidence Hub |
| Public runtime evidence | `audit/runtime/public-runtime-evidence-index.json` | Dashboard dinamico, Ops Dashboard |
| Public runtime validation | `audit/runtime/public-runtime-validation.json` | Ops Dashboard |
| Public runtime readiness | `audit/runtime/ops-readiness-report.json` | Ops Dashboard |
| Observability correlation | `artifacts/observability-correlation-report/observability-correlation-report.json` | Operational Evidence Hub |
| Artifact contract validation | `audit/artifact-contract-validation/artifact-contract-validation-report.json` | Operational Evidence Hub |
| Dashboard regression | `docs/dashboard/dashboard-regression-report.json` | Operational Evidence Hub |
| Living architecture traceability | `audit/living-architecture/living-architecture-traceability-report.json` | Operational Evidence Hub |

## Contratos associados

| Contrato | Finalidade |
|---|---|
| `docs/contracts/ci-lead-time-analytics.schema.json` | lead time |
| `docs/contracts/operational-history-snapshot.schema.json` | historico |
| `docs/contracts/runtime-predictive-analytics.schema.json` | risco preditivo |
| `docs/contracts/operational-maturity-score.schema.json` | maturidade |
| `docs/contracts/operational-artifact-discovery-index.schema.json` | descoberta |
| `docs/contracts/release-readiness.schema.json` | readiness |
| `docs/contracts/command-center-readiness.schema.json` | command center |
| `docs/contracts/contract-validation-report.schema.json` | validacao de contratos |

## Maturidade de evidencia

| Dimensao | Atual | Alvo | Gap |
|---|---:|---:|---:|
| Evidencias catalogadas | 96% | 99% | 3 p.p. |
| Contratos associados | 95% | 99% | 4 p.p. |
| Dashboard consumidor | 99% | 99% | 0 p.p. |
| Runbooks relacionados | 96% | 99% | 3 p.p. |

## Regras

- Evidencia report-only deve ser tratada como apoio operacional.
- Gates obrigatorios continuam sendo fonte decisoria principal para merge.
- Estado alvo nao deve ser confundido com estado evidenciado.
- Novos artifacts devem entrar neste indice na mesma rodada ou na rodada seguinte.
