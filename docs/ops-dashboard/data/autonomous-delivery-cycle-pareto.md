# Pareto — Autonomous Delivery Cycle

## 20% que resolve 80% do gargalo

1. Label explícita para autorização.
2. Validação de workflows obrigatórios verdes.
3. Merge com SHA esperado.
4. Observação pós-merge.
5. Fila report-only dos próximos incrementos.

## Por que isso acelera

- Elimina espera manual em PRs pequenos e verdes.
- Reduz polling manual de CI.
- Evita merge sem rastreabilidade.
- Mantém o próximo incremento já capturado.

## Por que não automatizar mais agora

- Execução automática de novos incrementos aumenta risco de regressão.
- Correção automática de CI vermelho pode mascarar causa raiz.
- A maturidade precisa ser medida após dry-runs e merges reais.
