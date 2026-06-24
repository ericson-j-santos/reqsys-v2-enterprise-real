# Requirement Quality Scoring Engine

## Objetivo

Calcular um score funcional de qualidade de requisitos usando os eventos da camada `ReqSys Product Intelligence Layer`.

## Capacidades implementadas

- Engine Python sem dependências externas.
- Cálculo de score funcional ponderado.
- Uso de BDD, ambiguidade, rastreabilidade, risco e prontidão.
- Classificação de maturidade funcional.
- Classificação de risco funcional.
- Recomendação objetiva de melhoria.
- Relatórios JSON, Markdown e HTML.
- Workflow CI dedicado.
- Artifact de scoring.

## Fórmula inicial

| Componente | Peso |
|---|---:|
| BDD coverage | 25% |
| Ambiguity quality | 20% |
| Traceability | 25% |
| Risk quality | 15% |
| Readiness | 15% |

Observação: `ambiguity_score` e `risk_score` são invertidos no cálculo, pois menor ambiguidade e menor risco aumentam a qualidade funcional.

## Níveis de maturidade

| Score | Nível |
|---:|---|
| 90–100 | GOLD |
| 75–89 | ADVANCED |
| 60–74 | CONTROLLED |
| 40–59 | PARTIAL |
| 0–39 | CRITICAL |

## Limites

- Não altera runtime produtivo.
- Não adiciona dependências externas.
- Não executa agentes automaticamente.
- Não integra bases corporativas reais.
- Não altera gates operacionais existentes.

## Próximo incremento recomendado

Functional Traceability Graph.
