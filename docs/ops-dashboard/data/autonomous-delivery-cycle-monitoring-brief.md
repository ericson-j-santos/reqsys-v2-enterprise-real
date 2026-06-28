# Monitoring brief — Autonomous Delivery Cycle

## Monitorar

- PRs com `cycle:auto-merge-approved`.
- PRs com `merge-queue:eligible`.
- Workflows obrigatórios no head SHA.
- Resultado do squash merge.
- Runs de `push` no merge commit.
- Fila `autonomous-delivery-cycle-next-increments.json`.

## Alertar

- PR autorizado mas não elegível.
- Workflow obrigatório ausente.
- CI pós-merge vermelho.
- Fila de próximos incrementos não vazia.
- Drift de nomes de workflows.

## Próximo incremento operacional

Criar card no dashboard consumindo `autonomous-delivery-cycle-latest.json`.
