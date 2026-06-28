# Changelog — Autonomous Delivery Cycle

## 2026-06-27

### Adicionado

- Workflow `.github/workflows/autonomous-delivery-cycle.yml`.
- Contrato `docs/ops-dashboard/data/autonomous-delivery-cycle-latest.json`.
- Fila report-only `docs/ops-dashboard/data/autonomous-delivery-cycle-next-increments.json`.
- Runbook `docs/runbooks/autonomous-delivery-cycle.md`.
- ADR `docs/architecture/autonomous-delivery-cycle.md`.
- Testes de contrato `tests/test_autonomous_delivery_cycle_contract.py`.

### Guardrails

- Exige label `cycle:auto-merge-approved`.
- Exige label `merge-queue:eligible`.
- Exige workflows obrigatórios verdes.
- Usa squash merge com SHA esperado.
- Observa CI pós-merge.
- Captura próximos incrementos como fila report-only.

### Fora do escopo

- Execução automática de novos incrementos.
- Correção automática de CI vermelho.
- Merge de PRs de alto risco sem autorização explícita.
