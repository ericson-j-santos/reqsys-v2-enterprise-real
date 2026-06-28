# Matriz de governança — Autonomous Delivery Cycle

| Controle | Obrigatório | Evidência |
|---|---:|---|
| Label `cycle:auto-merge-approved` | Sim | PR labels |
| Label `merge-queue:eligible` | Sim | PR labels |
| CI obrigatório verde | Sim | GitHub Actions runs |
| SHA esperado no merge | Sim | Pulls merge API |
| Squash merge | Sim | Merge method |
| Pós-merge observado | Sim | `delivery-cycle-report.json` |
| Próximos incrementos report-only | Sim | `autonomous-delivery-cycle-next-increments.json` |
| Execução automática do próximo incremento | Não | Guardrail |
