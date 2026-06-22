# Release Note — CI Router v1.0.0

## Resumo

Implementa roteamento de CI por paths para reduzir tempo de espera em PRs pequenos e consolidar a estratégia de Trunk-Based Development no ReqSys.

## Entregas

- `CI Router (paths + Pareto)`.
- Jobs condicionais para backend, frontend, documentação e Codex estático.
- `CI Router Result` como gate consolidado.
- Resumo visual no GitHub Step Summary.
- ADR-024 com decisão arquitetural.
- Runbook operacional.

## Benefício operacional

| Antes | Depois |
|---|---|
| CI completo mesmo em mudanças pequenas | CI proporcional à área alterada |
| Branches longas esperando validação ampla | PRs menores com feedback mais rápido |
| Pouca visibilidade do que rodou | resumo visual por área |
| Maior risco de retrabalho | roteamento objetivo e auditável |

## Critério de aceite

- Workflow `CI — ReqSys v2 Enterprise` executa o job router.
- PR de docs não roda backend/frontend completos.
- PR de backend roda backend lint/test.
- PR de frontend roda build/E2E.
- Alterações de workflow ou arquivos desconhecidos acionam CI completo.

## Próximo incremento recomendado

Adicionar comentário automático no PR com o resumo do CI Router e tempo estimado economizado por execução.
