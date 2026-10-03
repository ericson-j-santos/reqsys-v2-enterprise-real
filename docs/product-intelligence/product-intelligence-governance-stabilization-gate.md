# Product Intelligence Governance Stabilization Gate

## Objetivo

Avaliar se a camada Product Intelligence está estabilizada o suficiente para consolidação governada por revisão humana.

## Capacidades implementadas

- Gate Python sem dependências externas.
- Avaliação de índice mínimo de estabilidade.
- Avaliação de risco operacional máximo.
- Avaliação de confiança estatística mínima.
- Bloqueio por drifts abertos.
- Identificação de blockers e warnings.
- Relatórios JSON, Markdown e HTML.
- Workflow CI mínimo dedicado.

## Thresholds iniciais

| Métrica | Regra |
|---|---:|
| Stability index | mínimo 85 |
| Operational risk | máximo 12% |
| Statistical confidence | mínimo 82% |
| Drift count | máximo 0 |

## Estados

| Estado | Significado |
|---|---|
| STABILIZED_FOR_HUMAN_CONSOLIDATION | Estável para consolidação humana |
| STABILIZED_WITH_WARNINGS | Estável com alertas |
| NOT_STABILIZED | Não estabilizado |

## Limites

- Não faz deploy.
- Não altera produção.
- Não cria issues automaticamente.
- Não executa agentes automaticamente.
- Não chama IA externa.
- Não substitui aprovação humana.

## Próximo incremento recomendado

Product Intelligence Consolidated Governance Report.
