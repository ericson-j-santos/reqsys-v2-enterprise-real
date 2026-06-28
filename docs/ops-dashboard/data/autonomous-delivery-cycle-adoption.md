# Guia de adoção — Autonomous Delivery Cycle

## Adoção inicial

1. Mergear este incremento após CI verde.
2. Executar dry-run manual.
3. Corrigir eventual drift de workflow obrigatório.
4. Aplicar `cycle:auto-merge-approved` em um único PR pequeno.
5. Executar ciclo manual com `dry_run=false`.
6. Validar CI pós-merge.

## Adoção contínua

- Manter `max_prs=1` até histórico estável.
- Usar a fila de próximos incrementos apenas como recomendação.
- Não aumentar autonomia sem métricas de sucesso.

## Métricas mínimas antes de expandir

- 5 dry-runs consecutivos sem erro estrutural.
- 3 merges governados sem falha pós-merge.
- 0 merges sem label explícita.
- 0 falsos positivos de elegibilidade.
