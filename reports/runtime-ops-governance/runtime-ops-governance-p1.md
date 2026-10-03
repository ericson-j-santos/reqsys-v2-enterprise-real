# Runtime Ops Governance P1

## Estado executivo

| Campo | Valor |
|---|---|
| Modo | `review_only` |
| Estado | `NOT_READY` |
| Health score | 46 |
| Deployment confidence | low |
| Rollback policy | manual approval required with pre/post evidence snapshots |

## Runtime Health Center

| Fonte | Presente | Estado | Caminho |
|---|---:|---|---|
| ci_analytics | False | `UNKNOWN` | `reports/github-runtime-analytics/github-runtime-analytics.json` |
| operational_timeline | False | `UNKNOWN` | `reports/github-runtime-analytics/runtime-operational-correlation-timeline.json` |
| evidence_graph | False | `UNKNOWN` | `reports/github-runtime-analytics/runtime-operational-evidence-graph.json` |
| health_dashboard | True | `OPERATIONAL_HEALTH_DASHBOARD_READY` | `docs/operations/operational-health-dashboard.example.json` |
| product_readiness | False | `UNKNOWN` | `reports/product-intelligence/product-intelligence-runtime-readiness-gate.json` |

## CI Auto Remediation

Política de rerun: one safe rerun only for transient_infrastructure after evidence snapshot.

| Classe | Ação segura |
|---|---|
| `frontend_contract` | apply focused import/export fix and rebuild |
| `transient_infrastructure` | single governed rerun after cooldown |
| `dependency_security` | block deploy and open dependency remediation |
| `regression` | block rerun-only strategy; require code/test fix |

## Environment Drift Detector

| Ambiente | Variáveis obrigatórias | Segredos |
|---|---|---|
| dev | APP_ENV, DATABASE_URL, JWT_ISSUER, JWT_AUDIENCE, JWT_EXP_MINUTES, CORS_ORIGINS | fingerprint-only |
| hml | APP_ENV, DATABASE_URL, JWT_ISSUER, JWT_AUDIENCE, JWT_EXP_MINUTES, CORS_ORIGINS | fingerprint-only |
| prod | APP_ENV, DATABASE_URL, JWT_ISSUER, JWT_AUDIENCE, JWT_EXP_MINUTES, CORS_ORIGINS | fingerprint-only |
| flyio | APP_ENV, DATABASE_URL, JWT_ISSUER, JWT_AUDIENCE, JWT_EXP_MINUTES, CORS_ORIGINS | fingerprint-only |

## Runtime Evidence Consolidator

Artefatos gerados:

- `runtime-ops-governance-p1.json`
- `runtime-ops-governance-p1.md`
- `runtime-ops-governance-p1.html`

## Guardrails

- `no_deploy`
- `no_external_write`
- `no_secret_value_capture`
- `human_review_required`
