# Product Intelligence Governance Stability Index

## Objetivo

Gerar índice consolidado de estabilidade de governança da frente Product Intelligence a partir de snapshot, drift detector e executive control tower.

## Capacidades implementadas

- Gerador Python sem dependências externas.
- Índice ponderado de estabilidade.
- Classificação STABLE_GOLD, STABLE_CONTROLLED, WATCH ou REVIEW_REQUIRED.
- Consolidação de score governado, drift, controle, risco e confiança.
- Relatórios JSON, Markdown e HTML.
- Workflow CI mínimo dedicado.

## Fórmula inicial

| Componente | Peso |
|---|---:|
| Consolidated score | 30% |
| Drift score | 25% |
| Control score | 25% |
| Inverso do risco | 10% |
| Confiança estatística | 10% |

## Limites

- Não faz deploy.
- Não altera produção.
- Não cria issues automaticamente.
- Não executa agentes automaticamente.
- Não chama IA externa.
- Não substitui aprovação humana.

## Próximo incremento recomendado

Product Intelligence Governance Stabilization Gate.
