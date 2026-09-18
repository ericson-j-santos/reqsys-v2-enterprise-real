# Product Intelligence Governance Drift Detector

## Objetivo

Detectar desvios de governança da frente Product Intelligence comparando KPIs atuais com limites mínimos governados.

## Capacidades implementadas

- Detector Python sem dependências externas.
- Comparação de KPIs contra thresholds.
- Identificação de drifts e warnings.
- Score de drift.
- Estado de drift: NO_DRIFT, DRIFT_WITH_WARNINGS ou DRIFT_REVIEW_REQUIRED.
- Relatórios JSON, Markdown e HTML.
- Workflow CI mínimo dedicado.

## Thresholds iniciais

| Métrica | Threshold |
|---|---:|
| Product Intelligence maturity | 90% mínimo |
| Functional governance | 92% mínimo |
| Release evidence | 88% mínimo |
| Runtime planning | 80% mínimo |
| Estimated operational risk | 15% máximo |
| Statistical confidence | 80% mínimo |

## Limites

- Não faz deploy.
- Não altera produção.
- Não cria issues automaticamente.
- Não executa agentes automaticamente.
- Não chama IA externa.
- Não substitui aprovação humana.

## Próximo incremento recomendado

Product Intelligence Governance Stability Index.
