# Primeiro run — Autonomous Delivery Cycle

## Procedimento

1. Aguardar PR deste incremento ficar verde.
2. Mergear em `main`.
3. Acessar Actions.
4. Executar `Autonomous Delivery Cycle` com:
   - `dry_run=true`
   - `required_label=cycle:auto-merge-approved`
   - `max_prs=1`
5. Validar artifact `autonomous-delivery-cycle-report`.
6. Confirmar que nenhum merge foi executado em dry-run.

## Resultado esperado

- Workflow concluído com sucesso.
- Relatório publicado.
- Se não houver candidato, `candidate_count=0`.
- Se houver candidato sem label/fila/CI verde, blockers publicados.
