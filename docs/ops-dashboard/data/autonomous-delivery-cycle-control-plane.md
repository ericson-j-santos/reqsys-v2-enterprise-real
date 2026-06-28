# Control Plane — Autonomous Delivery Cycle

## Entrada

- PRs abertos em `main`.
- Labels `cycle:auto-merge-approved` e `merge-queue:eligible`.
- GitHub Actions do head SHA.

## Decisão

- Merge somente se todos os gates estiverem verdes.
- Bloqueios são publicados como artifact.

## Saída

- Squash merge opcional.
- Observação pós-merge.
- `delivery-cycle-report.json`.
- `autonomous-delivery-cycle-next-increments.json`.

## Integração com chat

O chat deve consumir a fila report-only e executar apenas o próximo incremento seguro após validar o estado real do repositório.
