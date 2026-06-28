# Plano de validação — Autonomous Delivery Cycle

## Validação no PR

- `python -m py_compile` não se aplica ao workflow YAML.
- `pytest tests/test_autonomous_delivery_cycle_contract.py` valida contratos e guardrails.
- Checks obrigatórios devem passar antes do merge.

## Validação pós-merge

1. Executar workflow manualmente com `dry_run=true`.
2. Confirmar artifact `autonomous-delivery-cycle-report`.
3. Confirmar que PR sem label `cycle:auto-merge-approved` não é mergeado.
4. Confirmar que PR sem `merge-queue:eligible` não é mergeado.
5. Confirmar publicação de `autonomous-delivery-cycle-next-increments.json`.

## Critério de sucesso

- Workflow executa sem erro em dry-run.
- Nenhum PR é mergeado sem autorização explícita.
- Relatório JSON é publicado mesmo sem candidatos.
- Próximo incremento fica capturado em fila report-only.
