# Burndown Executivo Operacional — ReqSys

## Objetivo

Estabelecer um modelo executivo para acompanhar evolução operacional do ReqSys com percentuais, maturidade, risco e lead time, mantendo distinção entre estado evidenciado e estado alvo.

## Baseline inicial

| Marco | Evidência | Impacto |
|---|---|---|
| PR #326 | Runtime observability foundation mergeado | Cria base de observabilidade runtime |
| Incidente de lead time | 143 minutos até estabilização verde | Define baseline de gargalo CI/CD |
| PR #327 | Redução de latência no post-merge validation | Reduz risco de fila e falso negativo |
| PR #328 | CI Lead Time Analytics | Cria métricas estatísticas de workflows |
| PR #329 | Estabilização do script analytics | Reduz risco técnico do artifact |

## Dimensões acompanhadas

| Dimensão | Fórmula inicial | Estado alvo |
|---|---|---:|
| Técnico | média de CI verde, testes e contrato preservado | >= 95% |
| Operacional | média de lead time, evidência e ruído controlado | >= 90% |
| Governança | gates obrigatórios, artifacts e rastreabilidade | >= 95% |
| Usuário final | disponibilidade funcional e navegação operacional | >= 90% |
| Produção | deploy, smoke público e health runtime | >= 95% |

## Indicadores mínimos por status

Todo relatório operacional deve trazer:

- percentual técnico;
- percentual operacional;
- percentual de governança;
- percentual de produção;
- lead time do PR ou workflow;
- taxa de sucesso;
- taxa de falha;
- P50 e P95 quando houver amostra;
- risco atual;
- próximo passo objetivo.

## Classificação de risco

| Condição | Risco |
|---|---|
| CI obrigatório vermelho | Alto |
| Evidence/report-only vermelho sem impacto em gate | Médio |
| P95 acima de 15 minutos | Médio |
| Max acima de 60 minutos | Alto |
| Falta de artifact esperado | Médio |
| Falha sem logs/artifacts | Alto |

## Burndown executivo inicial

| Item | Estado atual | Estado alvo | Gap |
|---|---:|---:|---:|
| Observabilidade CI/CD | 86% | 95% | 9 p.p. |
| Governança de artifacts | 84% | 95% | 11 p.p. |
| Rastreabilidade de lead time | 82% | 95% | 13 p.p. |
| Redução de falso negativo | 80% | 95% | 15 p.p. |
| Dashboard executivo integrado | 60% | 90% | 30 p.p. |

## Política de atualização

- Atualizar após cada PR mergeado.
- Não declarar padrão ouro sem evidência real.
- Separar implementado, validado, evidenciado, consolidado e governado.
- Links de PRs, workflows e artifacts devem acompanhar cada medição.

## Próximos incrementos recomendados

1. Integrar artifact `ci-lead-time-analytics.json` ao dashboard operacional.
2. Criar histórico versionado de burndown por data.
3. Publicar resumo executivo automático em artifact markdown.
4. Adicionar drill-down por workflow mais lento.
