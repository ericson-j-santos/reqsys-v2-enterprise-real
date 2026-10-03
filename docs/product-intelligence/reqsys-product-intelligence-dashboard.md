# ReqSys Product Intelligence Dashboard

## Objetivo

Consolidar evento funcional, score de qualidade e grafo de rastreabilidade em um dashboard funcional do ReqSys Product Intelligence Layer.

## Capacidades implementadas

- Gerador Python sem dependências externas.
- Consolidação de evento funcional.
- Consolidação de score de qualidade.
- Consolidação de grafo de rastreabilidade.
- Classificação de prontidão funcional.
- Relatórios JSON, Markdown e HTML.
- Workflow CI dedicado.
- Artifact de dashboard funcional.

## Indicadores

| Indicador | Descrição |
|---|---|
| Quality Score | Score funcional do requisito |
| Maturity | Nível de maturidade funcional |
| Risk Band | Faixa de risco funcional |
| Traceability Coverage | Cobertura de rastreabilidade |
| Product Readiness | Prontidão funcional consolidada |

## Estados de prontidão

| Estado | Critério inicial |
|---|---|
| READY_FOR_IMPLEMENTATION | Score >= 75 e rastreabilidade >= 60 |
| READY_FOR_REFINEMENT | Estado intermediário |
| NEEDS_REFINEMENT | Score < 40 ou rastreabilidade < 20 |

## Limites

- Não altera runtime produtivo.
- Não adiciona dependências externas.
- Não executa agentes automaticamente.
- Não integra bases corporativas reais.
- Não altera gates operacionais existentes.

## Próximo incremento recomendado

AI-assisted Product Decision Intelligence.
