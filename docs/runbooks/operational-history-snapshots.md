# Operational History Snapshots

## Objetivo

Publicar snapshots periódicos do estado operacional do ReqSys para criar histórico auditável de maturidade, risco, gaps e lead time.

## Artifact publicado

- `operational-history-snapshot.json`
- `operational-history-snapshot.md`

## Frequência

- Manual via `workflow_dispatch`.
- Agendada a cada 6 horas.
- Disparada quando o próprio workflow ou este runbook forem alterados na `main`.

## Métricas iniciais

| Métrica | Baseline | Alvo | Gap |
|---|---:|---:|---:|
| CI/CD | 90% | 95% | 5 p.p. |
| Governança | 91% | 95% | 4 p.p. |
| Observabilidade | 89% | 95% | 6 p.p. |
| Analytics operacional | 86% | 95% | 9 p.p. |
| Dashboard vivo | 78% | 90% | 12 p.p. |

## Governança

- Workflow report-only.
- Sem secrets.
- Sem escrita no repositório.
- Sem relaxamento de gates.
- Artifacts retidos por 30 dias.

## Próxima evolução

Persistir uma série histórica longa em storage governado ou branch dedicada de evidências, após validação de custo/ruído operacional.
