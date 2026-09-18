# Operational Artifact Discovery Index

## Objetivo

Criar um índice navegável dos artifacts operacionais do ReqSys para facilitar descoberta, consumo por dashboard e auditoria pós-merge.

## Artifacts operacionais atuais

| Artifact | Workflow | Uso |
|---|---|---|
| `ci-lead-time-analytics.json` | CI Lead Time Analytics | KPIs de lead time, P50, P95 e gargalos |
| `operational-history-snapshot.json` | Operational History Snapshot | Histórico, gaps e maturidade |
| `runtime-predictive-analytics.json` | Runtime Predictive Analytics | Score e nível de risco preditivo |
| `main-operational-post-merge-health.json` | Main Operational Post-Merge Health | Saúde pós-merge da main |
| `operational-artifact-schema-validation.json` | Operational Artifact Schema Validation | Validação de contratos dos artifacts |

## Contratos relacionados

| Artifact | Contrato |
|---|---|
| `ci-lead-time-analytics.json` | `docs/contracts/ci-lead-time-analytics.schema.json` |
| `operational-history-snapshot.json` | `docs/contracts/operational-history-snapshot.schema.json` |
| `runtime-predictive-analytics.json` | `docs/contracts/runtime-predictive-analytics.schema.json` |

## Política de navegação

Cada artifact deve possuir:

- workflow de origem;
- runbook;
- schema quando aplicável;
- dashboard consumidor quando aplicável;
- classificação de risco;
- modo operacional (`report-only` ou gate).

## Estado atual

| Dimensão | Maturidade |
|---|---:|
| Artifacts catalogados | 90% |
| Schemas catalogados | 95% |
| Dashboard consumidor | 92% |
| Rastreabilidade artifact → workflow | 88% |
| Rastreabilidade artifact → dashboard | 86% |

## Próximas evoluções

1. Gerar índice JSON automaticamente.
2. Exibir índice no dashboard dinâmico.
3. Vincular artifacts reais por `run_id`.
4. Adicionar histórico por artifact.
