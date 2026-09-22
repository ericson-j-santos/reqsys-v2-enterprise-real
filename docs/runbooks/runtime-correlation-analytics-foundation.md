# REQSYS#326 — Runtime Observability Foundation + Correlation Analytics

## Objetivo

Este incremento inicia a fundação de observabilidade runtime do ReqSys conectando `correlation_id`, runtime dashboard, evidence, incident timeline, workflows e ambientes sem dependência externa obrigatória e sem alterar deploy de produção.

## Contratos entregues

- `GET /api/runtime/analytics` consolida analytics runtime e expõe dois artifacts lógicos:
  - `runtime-correlation-report.json`
  - `runtime-observability-report.json`
- `GET /api/runtime/dashboard` inclui prévia navegável de:
  - correlation analytics;
  - incident correlation;
  - runtime topology preview;
  - operational trace chains;
  - environment dependency graph.

## Métricas de readiness

O bloco `observability_readiness` calcula:

| Métrica | Descrição |
| --- | --- |
| `observability_percent` | Média operacional de cobertura de topologia, visibilidade de incidentes, traceabilidade e estado runtime. |
| `topology_coverage` | Cobertura mínima das relações runtime/workflow/evidence. |
| `correlation_depth` | Profundidade da cadeia operacional correlacionada. |
| `incident_visibility` | Visibilidade de incidentes correlacionados no runtime. |
| `operational_traceability` | Percentual de rastreabilidade fim a fim da cadeia operacional. |

## Guardrails

- Read-only.
- Sem secrets e sem PII.
- Sem dependência externa obrigatória.
- Sem deploy destrutivo.
- Persistência segue o storage runtime analytics já existente.

## Validação local

```bash
cd backend
python -m pytest tests/test_runtime_analytics.py tests/test_runtime_page.py -q
```
