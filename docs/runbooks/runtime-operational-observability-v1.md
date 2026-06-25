# Runtime Operational Observability v1

## Objetivo

Adicionar uma camada leve e governada de observabilidade operacional em runtime para o ReqSys.

## Endpoints

| Endpoint | Uso |
|---|---|
| `/api/runtime/health` | snapshot JSON consolidado de saúde operacional |
| `/api/runtime/readiness` | prontidão operacional para tráfego controlado |
| `/api/runtime/liveness` | vida do processo/API |
| `/api/runtime/metrics` | métricas `text/plain` compatíveis com scraping operacional |

## Campos principais

- `correlation_id`
- `environment`
- `version`
- `status`
- `uptime_seconds`
- `risk_score`
- `runtime_health`
- `operational_summary`
- `critical_counts`
- `evidence`

## Guardrails

- Sem secrets.
- Sem PII.
- Sem relaxamento de gates de deploy.
- Sem alteração de deploy.
- Sem escrita em banco.
- Sem ação destrutiva.

## Critérios de aceite

- Endpoints retornam HTTP 200.
- `correlation_id` é propagado.
- Métricas não expõem HTML/script.
- `risk_score` permanece entre 0 e 100.
- Testes automatizados cobrem health, readiness, liveness e metrics.

## Próximo incremento recomendado

- Expor estes dados em dashboard navegável.
- Persistir snapshots históricos.
- Calcular MTTR, lead time e taxa de falha por janela temporal.
- Integrar com `CI Runtime Health Summary` e `CI Governance Drift Guard`.
