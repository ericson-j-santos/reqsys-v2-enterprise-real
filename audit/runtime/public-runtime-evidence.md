# Public Runtime Evidence — Audit Snapshot

- Repository: `reqsys-v2-enterprise-real`
- Generated at: `2026-06-27T17:04:56.958349+00:00`
- Run ID: `local-baseline`
- Strict gate passed: `False`
- Base URL: `https://reqsys-api.fly.dev`
- Operational status: `degraded`
- Readiness: `25.0%`
- Strict success: `25.0%` (1/4)

## Blocking issues
- /api/runtime/health: 404 HTTP Error 404: Not Found
- /api/runtime/readiness: 404 HTTP Error 404: Not Found
- /api/runtime/liveness: 404 HTTP Error 404: Not Found

## Nota operacional

- **fly_runtime_deploy_lag**: Os 404 nos endpoints strict do Fly indicam deploy anterior ao Runtime Operational Observability v1 — bloqueio evidenciado, fora do escopo wire-only (sem deploy). Corrigir exige incremento separado via ReqSys Fly Runtime P0 (workflow_dispatch deploy=true) antes de declarar produção healthy.
  - Próximo incremento: `fly-runtime-p0-deploy`
  - Bloqueia: `evidence-automation-observability-e2e`

## Consumers
- `docs/ops-dashboard/index.html`
- `scripts/generate_ops_dashboard_data.py`
- `docs/dashboard/live-operational-dashboard.dynamic.html`
