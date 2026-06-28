# Executive readout — Autonomous Delivery Cycle

## Decisão

Implementar ciclo governado de auto-merge condicionado.

## Valor

Reduz espera manual em PRs verdes e pequenos, mantendo rastreabilidade e bloqueios reais.

## Segurança

Não há merge sem:

- label explícita;
- fila governada elegível;
- workflows obrigatórios verdes;
- SHA esperado.

## Continuidade

Após merge, o ciclo captura próximos incrementos em fila report-only para execução posterior no chat/agente.

## Status

Implementado em branch. Pendente CI/merge/dry-run.
