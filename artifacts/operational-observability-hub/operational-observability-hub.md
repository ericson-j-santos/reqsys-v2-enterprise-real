# Operational Observability Hub

- Correlation ID: `a4c53fd1-e5a9-42e0-9952-b8d4cb122ae7`
- Status: `degraded`
- Risk: `high`
- Correlation chain events: `4`

## Pareto increment

- `multi_environment_evidence`: `True`
- `metrics_history_persisted`: `False`
- `longitudinal_analytics`: `False`
- `environment_drift_detection`: `True`
- `governed_alerts`: `True`
- `slo_sla_evidence`: `True`
- `ci_runtime_observability_correlation`: `True`

## Governed alert

- Level: `HIGH` · Type: `ENVIRONMENT_DRIFT` · Policy: `MANUAL_REVIEW_REQUIRED`

## Recommended actions

- Normalizar URLs de dev entre validate_environments_readiness e fly-environments.
- Normalizar URLs de hml entre validate_environments_readiness e fly-environments.
- Normalizar URLs de prod entre validate_environments_readiness e fly-environments.
- Tratar breach SLO env_probe_availability: actual=0.0%
- Alerta governado HIGH: ENVIRONMENT_DRIFT — MANUAL_REVIEW_REQUIRED
