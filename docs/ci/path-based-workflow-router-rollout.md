# Rollout — Path-Based Workflow Router

## Fase 1

Aplicar `paths` somente em workflows advisory/report-only selecionados.

## Fase 2

Observar PRs pequenos e comparar quantidade de workflows disparados antes/depois.

## Fase 3

Expandir para outros workflows report-only, mantendo:

- `ReqSys Required Fast Gate` sempre executado;
- segurança crítica preservada;
- deploy/smoke produtivo fora de PR comum;
- execução manual disponível por `workflow_dispatch`.
