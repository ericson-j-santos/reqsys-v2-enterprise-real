# PR Summary — Autonomous Delivery Cycle

## Objetivo

Implementar ciclo governado para:

- validar PRs verdes;
- executar merge automático somente com autorização explícita;
- monitorar CI pós-merge;
- capturar próximos incrementos para continuidade no chat/agente.

## Escopo técnico

- Novo workflow GitHub Actions.
- Contratos JSON para dashboard e agentes.
- Fila report-only de próximos incrementos.
- ADR, runbook, changelog, prompts e testes de contrato.

## Risco

Baixo a médio.

Mitigação principal: merge só ocorre com `cycle:auto-merge-approved`, `merge-queue:eligible`, workflows obrigatórios verdes e SHA esperado.

## Próximo incremento natural

Consumir os contratos do ciclo no dashboard operacional com cards de estado, bloqueios, pós-merge e fila de próximos incrementos.
