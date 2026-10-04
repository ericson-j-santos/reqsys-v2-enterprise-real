# Trilha B — Observabilidade Enterprise

**Data:** 2026-06-27  
**ADR:** [`docs/adr/ADR-037-trilha-b-observabilidade-enterprise.md`](../adr/ADR-037-trilha-b-observabilidade-enterprise.md)

## Objetivo

Operar correlation_id, métricas por feature, telemetria operacional e tracing opcional — sem alterar deploy.

## Artefatos canônicos

| Item | Caminho |
|---|---|
| Architecture-as-Code | [`docs/architecture/trilha-b/architecture-as-code.json`](../architecture/trilha-b/architecture-as-code.json) |
| Middleware | [`backend/app/middleware/observability.py`](../../backend/app/middleware/observability.py) |
| Métricas | [`backend/app/core/feature_metrics.py`](../../backend/app/core/feature_metrics.py) |
| Correlation | [`backend/app/core/correlation.py`](../../backend/app/core/correlation.py) |
| OpenTelemetry | [`backend/app/core/otel.py`](../../backend/app/core/otel.py) |
| Schema | [`docs/contracts/trilha-b-observabilidade-enterprise.schema.json`](../contracts/trilha-b-observabilidade-enterprise.schema.json) |
| Gerador | [`scripts/trilha_b_observabilidade_enterprise.py`](../../scripts/trilha_b_observabilidade_enterprise.py) |
| Workflow | [`.github/workflows/trilha-b-observabilidade-enterprise.yml`](../../.github/workflows/trilha-b-observabilidade-enterprise.yml) |

## Endpoints

| Método | Rota | Função |
|---|---|---|
| GET | `/health` | Propaga `X-Correlation-Id` na resposta |
| GET | `/api/runtime/metrics` | Prometheus-style feature metrics |
| GET | `/api/runtime/analytics` | `operational_telemetry` com correlation |

## Validação local

```bash
cd backend && . .venv/bin/activate
python -m pytest tests/test_observability_enterprise.py -v
python ../scripts/trilha_b_observabilidade_enterprise.py
cat ../audit/trilha-b/trilha-b-observabilidade-enterprise-report.json
```

## Critério de pronto

1. Middleware propaga correlation_id em todas as respostas relevantes.
2. Métricas expõem label `feature`.
3. Testes `test_observability_enterprise.py` verdes.
4. Workflow publica artifact `trilha-b-observabilidade-enterprise-${{ github.run_id }}`.

## Relação com outras trilhas

- **Trilha C** consome telemetria na UX operacional.
- **Trilha E** indexa módulos de API em inventory.
