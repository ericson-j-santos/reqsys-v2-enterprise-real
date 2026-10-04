# ADR — Analytics Runtime Intelligence e Operational Sync

## Status

Implementação reconciliada com governança fail-closed.

## Contexto

O PR #81 propõe uma camada de Analytics Runtime Intelligence (ARI) e um Operational Sync Engine. A versão histórica confundia contrato/samples locais com readiness de produção.

## Decisão

1. ARI expõe síntese analítica e matriz de readiness.
2. O endpoint canônico para a UI é `/api/analytics-runtime-intelligence/snapshot`; `/v1/.../snapshot` permanece alias.
3. Samples locais e validação estática de SQL nunca são evidência de produção.
4. Staging é fail-closed sem URL externa, readback visual e smoke explicitamente fornecidos.
5. Telemetria e lineage de contrato não equivalem a exportação/lineage reais.
6. Figma permanece evidência pendente até existir readback atual verificável.
7. Operational Sync não contém estados hardcoded de PRs; consome somente input explícito e, sem input, retorna `evidence_required`.
8. `/monitoramento-operacional` continua sendo a fonte canônica do estado técnico corrente.

## Consequência

O sistema pode evoluir capacidades analíticas sem gerar falso verde de maturidade ou production readiness.
