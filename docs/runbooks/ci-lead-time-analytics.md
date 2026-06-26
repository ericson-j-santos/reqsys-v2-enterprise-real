# CI Lead Time Analytics

## Objetivo

Criar uma evidência operacional periódica para medir o tempo de execução dos workflows do ReqSys e reduzir gargalos como o caso observado no PR #326, em que o ciclo até estabilização verde levou aproximadamente 143 minutos.

## Escopo

O workflow `CI Lead Time Analytics` coleta as últimas execuções de GitHub Actions do repositório e publica artifact com:

- quantidade de runs analisadas;
- taxa de sucesso;
- taxa de falha;
- lead time médio;
- P50;
- P95;
- maior duração observada;
- top gargalos por workflow;
- baseline do incidente de 143 minutos.

## Artefatos publicados

- `ci-lead-time-analytics.json`
- `ci-lead-time-analytics.md`

## Política operacional

Este workflow é `report-only`.

Ele não substitui nem relaxa os gates obrigatórios:

- `CI — ReqSys v2 Enterprise`;
- `Governance Quality Gates`;
- `Governança Padrão Ouro`.

## Limites e interpretação

- P95 alto indica gargalo recorrente, não necessariamente falha funcional.
- Taxa de sucesso baixa indica risco operacional e exige triagem.
- Duração máxima alta pode ser evento isolado, mas deve alimentar o burndown executivo quando recorrente.
- O baseline de 143 minutos deve ser usado como referência histórica para validar evolução de eficiência.

## Critérios de melhoria

| Indicador | Alvo inicial |
|---|---:|
| Success rate | >= 95% |
| Failure rate | <= 5% |
| P95 lead time | < 15 minutos |
| Max lead time recorrente | < 60 minutos |
| Evidência publicada | 100% das execuções agendadas |

## Próxima evolução recomendada

Integrar o artifact `ci-lead-time-analytics.json` ao dashboard operacional para exibir tendência histórica, gargalos e delta antes/depois por PR.
