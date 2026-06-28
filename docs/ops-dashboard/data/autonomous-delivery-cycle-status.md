# Autonomous Delivery Cycle — status executivo

| Indicador | Estado alvo |
|---|---|
| Auto-merge governado | Ativo somente com label explícita |
| CI obrigatório | Todos verdes antes do merge |
| Pós-merge | Observação de runs `push` |
| Próximos incrementos | Captura report-only |
| Execução automática de incremento | Não autorizada |
| Risco operacional | Baixo, condicionado aos guardrails |

## Fluxo

```mermaid
flowchart TD
  A[PR aberto] --> B{Label cycle:auto-merge-approved?}
  B -- não --> X[Bloqueia ciclo]
  B -- sim --> C{Label merge-queue:eligible?}
  C -- não --> X
  C -- sim --> D{Workflows obrigatórios verdes?}
  D -- não --> X
  D -- sim --> E[Squash merge com SHA esperado]
  E --> F[Observar CI pós-merge em main]
  F --> G[Publicar delivery-cycle-report.json]
  G --> H[Capturar próximos incrementos report-only]
```

## Próxima ação recomendada

Após merge deste incremento, executar o workflow em `dry_run=true`. Se o relatório sair limpo, aplicar a label `cycle:auto-merge-approved` apenas nos PRs pequenos, verdes e de baixo risco.
