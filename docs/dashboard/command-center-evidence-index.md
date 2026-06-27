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
| Readiness do command center | `audit/command-center/command-center-readiness.json` | Dashboard dinamico |
| Validacao de contratos | `audit/extended-contract-validation/extended-operational-contract-validation.json` | Dashboard dinamico |
| Projecao de conclusao | `audit/projection/completion-projection-report.json` | Dashboard dinamico |

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
| `docs/contracts/completion-projection-report.schema.json` | projecao de conclusao |

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
