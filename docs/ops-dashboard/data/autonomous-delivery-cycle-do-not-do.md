# Autonomous Delivery Cycle — limites operacionais

## Não fazer

- Não aplicar `cycle:auto-merge-approved` em PR grande, estrutural ou de alto risco sem revisão humana.
- Não tratar o ciclo como substituto de code review.
- Não reduzir a lista de workflows obrigatórios sem evidência.
- Não habilitar `max_prs` alto antes de histórico verde.
- Não executar próximo incremento automaticamente só porque foi capturado na fila.
- Não ignorar falha pós-merge.
- Não usar force merge.
- Não alterar branch protection para contornar gate.

## Quando parar

- `main` vermelho.
- PR com conflito.
- PR sem `merge-queue:eligible`.
- Workflow obrigatório ausente.
- Pós-merge com falha.
- Próximo incremento sem escopo claro.
