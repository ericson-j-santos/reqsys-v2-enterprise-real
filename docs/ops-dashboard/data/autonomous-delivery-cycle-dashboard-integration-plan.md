# Plano de integração ao dashboard — Autonomous Delivery Cycle

## Objetivo

Renderizar no dashboard operacional:

- estado do ciclo;
- PRs candidatos;
- blockers;
- pós-merge;
- fila de próximos incrementos.

## Arquivos de entrada

- `docs/ops-dashboard/data/autonomous-delivery-cycle-latest.json`
- `docs/ops-dashboard/data/autonomous-delivery-cycle-next-increments.json`
- `docs/ops-dashboard/data/autonomous-delivery-cycle-dashboard-card.json`

## Fallback

Se os arquivos não existirem:

- exibir estado `not_available`;
- não quebrar dashboard;
- orientar executar primeiro dry-run.

## Próximo incremento natural

Implementar seção/cards no `docs/ops-dashboard/index.html`.
