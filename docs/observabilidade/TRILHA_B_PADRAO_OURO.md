# Trilha B — Observabilidade Enterprise (Padrão Ouro)

> Status: **canônico**  
> Precedência: complementa `ADR-0005` e `OBSERVABILIDADE_PADRAO.md`  
> Escopo: backend FastAPI, frontend Vue, runtime analytics e CI

## Objetivo

Estabelecer a **Trilha B** como padrão ouro obrigatório de observabilidade enterprise no ReqSys, cobrindo:

1. OpenTelemetry (opt-in)
2. Tracing distribuído
3. `correlation_id` ponta a ponta
4. Analytics operacional
5. Métricas por feature

## Pilares canônicos

| Pilar | Implementação canônica | Evidência |
| --- | --- | --- |
| `correlation_id` | Middleware HTTP global + envelope + frontend por sessão | `backend/app/middleware/observability.py`, `frontend/src/services/api.js` |
| `distributed_tracing` | OpenTelemetry FastAPI/httpx + atributo `reqsys.correlation_id` | `backend/app/core/otel.py` |
| `feature_metrics` | Contadores in-process por feature + Prometheus | `backend/app/core/feature_metrics.py`, `/api/runtime/metrics` |
| `operational_analytics` | Telemetria agregada em runtime analytics | `/api/runtime/analytics` → `operational_telemetry` |
| `structured_logging` | `telemetry.log_evento` por request | `backend/app/core/telemetry.py` |

## Fluxo padrão ouro

```text
Cliente (session correlation_id)
  → Middleware observability (correlation + métricas + log)
    → Handler FastAPI (envelope com meta.correlation_id)
      → Serviços/integrações (propagação)
        → /api/runtime/analytics (operational_telemetry)
          → /api/runtime/metrics (Prometheus por feature)
```

## Drill-down operacional

```text
Indicador runtime → /api/runtime/dashboard → /api/runtime/analytics → log correlacionado → ação operacional
```

## Gates bloqueantes (produção)

Produção deve ser bloqueada quando:

- request sem `correlation_id` rastreável em fluxo crítico;
- auditoria sem `correlation_id`;
- log com PII, token, senha ou connection string;
- métricas runtime indisponíveis (`/api/runtime/metrics`);
- analytics operacional sem `operational_telemetry`;
- `trilha_b_gold_standard.status` = `missing` em validação de release.

## Ativação OpenTelemetry

```bash
OTEL_ENABLED=true
OTEL_SERVICE_NAME=reqsys-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces  # opcional
```

Sem `OTEL_ENABLED`, a Trilha B permanece válida com correlation, métricas e analytics locais.

## Checklist padrão ouro — Trilha B

- [ ] Middleware de observabilidade registrado em `main.py`
- [ ] `correlation_id` no header de resposta e no envelope
- [ ] Frontend reutiliza correlation por sessão
- [ ] Métricas Prometheus por feature expostas
- [ ] Analytics operacional com `operational_telemetry`
- [ ] Testes `test_observability_enterprise.py` verdes
- [ ] Documentação e ADR atualizados
- [ ] OTEL ativado em staging/prod quando houver coletor

## Validação automática

```bash
cd backend
python -m pytest tests/test_observability_enterprise.py -v
python -c "from app.core.observability_gold_standard import avaliar_trilha_b; import json; print(json.dumps(avaliar_trilha_b(), indent=2, ensure_ascii=False))"
```

Endpoint runtime:

```http
GET /api/runtime/observability/gold-standard
```

## Decisão canônica

A Trilha B substitui implementações paralelas de correlation por rota. Novas features devem:

- reutilizar o middleware existente;
- registrar métricas via `feature_metrics`;
- expor drill-down em analytics quando aplicável;
- não criar resolvers duplicados de `correlation_id`.
