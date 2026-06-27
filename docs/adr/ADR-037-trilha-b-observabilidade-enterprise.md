# ADR-037 — Trilha B: Observabilidade Enterprise

## Status

Aceito em 2026-06-27.

## Contexto

O ReqSys já propagava `correlation_id` e expunha métricas operacionais, mas faltava empacotar observabilidade enterprise como trilha governada com validador, runbook e architecture-as-code — alinhada ao padrão ouro transversal.

## Decisão

Formalizar a **Trilha B — Observabilidade Enterprise** com quatro capacidades:

| Capacidade | Artefato |
|---|---|
| Correlation ID | `backend/app/core/correlation.py`, middleware |
| Métricas por feature | `backend/app/core/feature_metrics.py`, `/api/runtime/metrics` |
| Telemetria operacional | `/api/runtime/analytics` → `operational_telemetry` |
| Tracing opcional | `backend/app/core/otel.py` (desabilitado por padrão) |

Validação report-only via `scripts/trilha_b_observabilidade_enterprise.py` e workflow dedicado.

## Regras de governança

| Tema | Decisão |
|---|---|
| Modo | `report_only` |
| Logs | Nunca expor token, senha, CPF, PII ou connection string |
| Correlation | Aceitar `X-Correlation-ID` ou `X-Request-ID`; propagar em resposta e auditoria |
| OpenTelemetry | Opt-in via configuração; desabilitado por padrão em dev/CI |

## Consequências

### Benefícios

- Observabilidade rastreável e testável como pacote de produto.
- Base para drill-down operacional nas trilhas C e E.

### Limitações

- Métricas in-process; não substitui Prometheus/Grafana externo.
- OTEL completo fica para incremento futuro.

## Referências

- `docs/adr/ADR-0005-observabilidade-auditoria.md`
- `docs/runbooks/trilha-b-observabilidade-enterprise.md`
- `backend/tests/test_observability_enterprise.py`
