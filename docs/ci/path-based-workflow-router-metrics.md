# Métricas — Path-Based Workflow Router

## Indicadores recomendados

| Indicador | Como medir |
|---|---|
| Workflows por PR | Contagem de runs associados ao head SHA |
| Tempo até primeiro check verde | Diferença entre criação do PR e conclusão do gate rápido |
| Tempo total de checks | Maior duração entre workflows disparados |
| Workflows report-only disparados | Contagem de workflows advisory executados no PR |
| Retrabalho por CI vermelho | Quantidade de commits corretivos após falha de workflow |

## Critério de sucesso

Redução progressiva da quantidade de workflows em PRs pequenos, preservando o `ReqSys Required Fast Gate` como evidência mínima obrigatória.
