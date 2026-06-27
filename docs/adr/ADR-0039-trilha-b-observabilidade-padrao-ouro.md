# ADR-0039 — Trilha B como Padrão Ouro de Observabilidade Enterprise

Status: aceito  
Data: 2026-06-27  
Relacionado: ADR-0005, `docs/observabilidade/TRILHA_B_PADRAO_OURO.md`

## Contexto

O ReqSys já possuía `correlation_id`, runtime analytics e métricas Prometheus parciais, mas sem contrato único de observabilidade enterprise. Havia resolvers duplicados por rota, IDs por request no frontend e ausência de OpenTelemetry.

## Decisão

Adotar a **Trilha B — Observabilidade Enterprise** como padrão ouro canônico, com cinco pilares:

1. **OpenTelemetry** — opt-in via `OTEL_ENABLED`
2. **Tracing distribuído** — W3C TraceContext + `reqsys.correlation_id`
3. **correlation_id** — middleware global, envelope automático, frontend por sessão
4. **Analytics operacional** — `operational_telemetry` em `/api/runtime/analytics`
5. **Métricas por feature** — Prometheus em `/api/runtime/metrics`

## Consequências

- Reduz conflito entre rotas ao centralizar correlation no middleware.
- Permite drill-down operacional sem novo motor de analytics.
- OTEL permanece opcional para dev local sem coletor.
- Validação automática via `avaliar_trilha_b()` e endpoint gold-standard.

## Critérios de aceite

- Middleware ativo em todas as requisições HTTP.
- Header `X-Correlation-Id` na resposta.
- `meta.correlation_id` no envelope quando aplicável.
- Métricas `reqsys_http_*` por feature no scrape Prometheus.
- `operational_telemetry` no analytics runtime.
- Testes enterprise verdes em CI.
