# PR body draft — Autonomous Delivery Cycle

## Objetivo

Implementar o ciclo governado para automatizar merge de PRs verdes e autorizados, observar CI pós-merge e capturar próximos incrementos para continuidade no chat/agente.

## Escopo

- Novo workflow `Autonomous Delivery Cycle`.
- Contratos JSON para dashboard e agentes.
- Fila report-only de próximos incrementos.
- Runbook, ADR, changelog, prompts e testes de contrato.

## Guardrails

- Exige `cycle:auto-merge-approved`.
- Exige `merge-queue:eligible`.
- Exige workflows obrigatórios verdes.
- Usa squash merge com SHA esperado.
- Observa CI pós-merge.
- Não executa próximo incremento automaticamente.

## Próximo incremento natural

Consumir os contratos do ciclo no dashboard operacional com cards de status, blockers, pós-merge e fila de próximos incrementos.
