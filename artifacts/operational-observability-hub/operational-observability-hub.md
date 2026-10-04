# Operational Observability Hub

- Correlation ID: `b144b9bf-e508-4743-b85e-0d56eba88727`
- Status: `watch`
- Risk: `medium`
- Correlation chain events: `5`

## Pareto increment

- `multi_environment_evidence`: `True`
- `metrics_history_persisted`: `False`
- `longitudinal_analytics`: `False`
- `environment_drift_detection`: `True`
- `governed_alerts`: `True`
- `slo_sla_evidence`: `True`
- `ci_runtime_observability_correlation`: `True`
- `contract_artifacts_hydrated`: `True`
- `openapi_validation_available`: `False`
- `routes_drift_available`: `False`
- `semantic_diff_available`: `False`

## Governed alert

- Level: `MEDIUM` · Type: `ENVIRONMENT_DRIFT` · Policy: `MANUAL_REVIEW_REQUIRED`

## Recommended actions

- Alinhar disponibilidade entre ambientes promoviveis.
- Tratar breach SLO env_probe_availability: actual=66.67%
- Alerta governado MEDIUM: ENVIRONMENT_DRIFT — MANUAL_REVIEW_REQUIRED
- Tratar gap de sincronização contrato: semantic_backend_route_sync_pending
