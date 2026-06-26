# Contrato de KPIs — CI Lead Time Analytics

## Objetivo

Formalizar o contrato do artifact `ci-lead-time-analytics.json` para permitir consumo futuro por dashboards, evidências operacionais, burndown executivo e validações automatizadas.

## Artifact governado

- Nome lógico: `ci-lead-time-analytics.json`
- Schema: `docs/contracts/ci-lead-time-analytics.schema.json`
- Modo: report-only
- Fonte: GitHub Actions API
- Permissões esperadas: `actions: read` e `contents: read`

## KPIs obrigatórios

| KPI | Tipo | Uso operacional |
|---|---|---|
| `success_rate_percent` | percentual | Saúde geral do CI |
| `failure_rate_percent` | percentual | Risco de instabilidade |
| `avg_seconds` | segundos | Lead time médio |
| `p50_seconds` | segundos | Mediana operacional |
| `p95_seconds` | segundos | Gargalo recorrente |
| `max_seconds` | segundos | Pior caso observado |
| `baseline_incident_minutes` | minutos | Referência histórica do incidente de 143 minutos |
| `bottlenecks` | lista | Top workflows por P95 |

## Classificação executiva

| Condição | Status operacional |
|---|---|
| `success_rate_percent >= 95` e `p95_seconds < 900` | Verde |
| `success_rate_percent >= 90` ou `p95_seconds < 3600` | Amarelo |
| `success_rate_percent < 90` ou `max_seconds >= 3600` | Vermelho |

## Regras de governança

- O artifact não deve conter secrets, tokens ou payloads sensíveis.
- URLs de workflow podem ser publicadas como rastreabilidade operacional.
- O workflow é report-only e não deve substituir gates obrigatórios.
- Mudanças incompatíveis devem incrementar `schema_version`.

## Estado atual evidenciado

O baseline foi criado após o caso do PR #326, cujo tempo até estabilização verde foi informado como aproximadamente 143 minutos.

## Próxima evolução

Adicionar validação automática do schema JSON assim que houver artifact de exemplo versionado no repositório ou em artifact persistido consumível pelo pipeline.
