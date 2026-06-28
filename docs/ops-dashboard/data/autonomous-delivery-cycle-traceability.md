# Rastreabilidade — Autonomous Delivery Cycle

| Requisito | Evidência |
|---|---|
| Validar PR verde | `.github/workflows/autonomous-delivery-cycle.yml` |
| Exigir autorização explícita | `cycle:auto-merge-approved` |
| Exigir fila governada | `merge-queue:eligible` |
| Mergear com segurança | squash + SHA esperado |
| Monitorar pós-merge | `post_merge` em `delivery-cycle-report.json` |
| Capturar próximos incrementos | `autonomous-delivery-cycle-next-increments.json` |
| Documentar operação | `docs/runbooks/autonomous-delivery-cycle.md` |
| Validar contrato | `tests/test_autonomous_delivery_cycle_contract.py` |
