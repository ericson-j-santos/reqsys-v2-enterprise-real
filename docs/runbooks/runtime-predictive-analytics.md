# Runtime Predictive Analytics

## Objetivo

Criar uma camada inicial de analytics preditivo report-only para antecipar risco operacional do ReqSys com base em success rate, failure rate, P95 e max lead time.

## Modelo inicial

| Entrada | Peso operacional |
|---|---:|
| Success rate abaixo de 95% | médio |
| Failure rate acima de 5% | alto |
| P95 acima de 15 minutos | médio |
| Max acima de 60 minutos | alto |

## Saídas

- `risk_score` de 0 a 100;
- `risk_level` (`low`, `medium_low`, `medium`, `high`);
- lista de predições;
- recomendações operacionais;
- guardrails de segurança.

## Artifacts publicados

- `runtime-predictive-analytics.json`
- `runtime-predictive-analytics.md`

## Governança

- Modo report-only.
- Não relaxa gates obrigatórios.
- Não altera deploy/runtime.
- Não usa secrets além do token padrão de leitura do workflow.
- Não executa remediação automática.

## Interpretação executiva

| Risk score | Classificação | Ação |
|---|---|---|
| 0 a 14.99 | baixo | monitorar |
| 15 a 34.99 | médio/baixo | acompanhar tendência |
| 35 a 69.99 | médio | abrir triagem objetiva |
| 70 a 100 | alto | priorizar correção operacional |

## Limites

Este modelo é heurístico inicial. Não deve ser tratado como previsão estatística consolidada sem série histórica suficiente.

## Próximas evoluções

1. Consumir automaticamente `ci-lead-time-analytics.json`.
2. Integrar snapshots históricos.
3. Calcular tendência real por janela temporal.
4. Exibir score no dashboard dinâmico.
