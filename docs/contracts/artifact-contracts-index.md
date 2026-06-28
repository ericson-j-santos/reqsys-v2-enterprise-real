# Artifact Contracts Index

Índice operacional dos artifacts JSON inventariados em workflows e documentação. Esta camada é report-only e não altera a geração atual dos artifacts.

## Contrato mínimo

Todo artifact operacional JSON deve convergir para os campos mínimos:

- `generated_at`
- `source`
- `status`
- `confidence_level`
- `maturity_percent`
- `operational_risk`
- `commit_sha`
- `workflow_run_id when applicable`

## Workflow de validação

- Workflow: `.github/workflows/artifact-contract-validation.yml`.
- Script: `scripts/artifact_contract_validator.py`.
- Saídas publicadas: `artifact-contract-validation-report.json` e `artifact-contract-validation-report.md` no artifact `artifact-contract-validation-report-${{ github.run_id }}`.
- Modo: report-only / não bloqueante nesta versão inicial.

## Schemas

| Schema | Uso |
|---|---|
| `docs/contracts/agent-output.schema.json` | Contrato de saída padronizada para agentes especializados. |
| `docs/contracts/artifact-contract-validation-report.schema.json` | Contrato do relatório desta validação. |
| `docs/contracts/ci-lead-time-analytics.schema.json` | Contrato específico existente. |
| `docs/contracts/command-center-readiness.schema.json` | Contrato específico existente. |
| `docs/contracts/contract-validation-report.schema.json` | Contrato específico existente. |
| `docs/contracts/delivery-burndown-snapshot.schema.json` | Contrato específico existente. |
| `docs/contracts/delivery-evidence-report.schema.json` | Contrato específico existente. |
| `docs/contracts/delivery-readiness-report.schema.json` | Contrato específico existente. |
| `docs/contracts/delivery-status-report.schema.json` | Contrato específico existente. |
| `docs/contracts/operational-artifact-discovery-index.schema.json` | Contrato específico existente. |
| `docs/contracts/operational-history-index.schema.json` | Contrato específico existente. |
| `docs/contracts/operational-history-snapshot.schema.json` | Contrato específico existente. |
| `docs/contracts/operational-json-artifact.schema.json` | Contrato base para artifacts JSON sem schema específico. |
| `docs/contracts/operational-maturity-score.schema.json` | Contrato específico existente. |
| `docs/contracts/release-readiness.schema.json` | Contrato específico existente. |
| `docs/contracts/runtime-predictive-analytics.schema.json` | Contrato específico existente. |

## Inventário atual

| Artifact | Source | Schema | Workflows |
|---|---|---|---|
| `${REPORT_DIR}/pr-ci-watch.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/pr-ci-watch.yml |
| `${REPORT_DIR}/request.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/fly-governed-command-center.yml |
| `${REPORT_DIR}/request.validated.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/fly-governed-command-center.yml |
| `${REPORT_DIR}/runtime-health.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/runtime-operational-health.yml |
| `.schema.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/extended-operational-contract-validation.yml, .github/workflows/operational-artifact-schema-validation.yml |
| `/tmp/bandit-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ci-security.yml |
| `/tmp/failure-patterns.pretty.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/failure-pattern-engine.yml |
| `/tmp/npm-audit-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ci-security.yml |
| `/tmp/pip-audit-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ci-security.yml, .github/workflows/ci.yml |
| `/tmp/ruff-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ci.yml |
| `/tmp/runtime-health-report.pretty.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/runtime-health-center.yml |
| `artifacts/ci-runtime-health-summary/summary.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ci-runtime-health-summary.yml |
| `artifacts/deep-diagnostic/classification/failure-pattern-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/actions-deep-diagnostic.yml |
| `artifacts/deep-diagnostic/deep-diagnostic.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-center-history.yml, .github/workflows/operational-center-html.yml, .github/workflows/operational-intelligence-hub.yml |
| `artifacts/deep-governance-review/request.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/deep-governance-review.yml |
| `artifacts/deep-governance-review/request.validated.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/deep-governance-review.yml |
| `artifacts/failure-pattern-engine/failure-pattern-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/failure-pattern-engine.yml, .github/workflows/operational-center-history.yml, .github/workflows/operational-center-html.yml, .github/workflows/operational-intelligence-hub.yml |
| `artifacts/governed-dev-automerge/policy.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/governed-dev-automerge.yml |
| `artifacts/governed-dev-automerge/pr.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/governed-dev-automerge.yml |
| `artifacts/governed-promotion/promotion-policy.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/governed-promotion-pipeline.yml |
| `artifacts/main-operational-health/evidence.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/main-operational-health.yml |
| `artifacts/main-smoke-ci/evidence.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/main-smoke-ci.yml |
| `artifacts/manual-gate-guardrail/evidence.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/manual-gate-guardrail.yml |
| `artifacts/operational-ci-intelligence/input/runs.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-center-history.yml, .github/workflows/operational-center-html.yml, .github/workflows/operational-ci-intelligence.yml, .github/workflows/operational-intelligence-hub.yml |
| `artifacts/operational-ci-intelligence/operational-ci-intelligence.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-center-history.yml, .github/workflows/operational-center-html.yml, .github/workflows/operational-intelligence-hub.yml |
| `artifacts/operational-drift-analyzer/operational-drift-analyzer.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-executive-dashboard.yml |
| `artifacts/operational-governance-gate/operational-governance-gate.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-executive-dashboard.yml, .github/workflows/operational-risk-engine.yml |
| `artifacts/operational-governance-orchestrator/operational-governance-orchestrator.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-governance-orchestrator.yml |
| `artifacts/operational-health.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/reqsys-operational-health.yml |
| `artifacts/operational-health/evidence.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-health-dashboard.yml |
| `artifacts/operational-health/operational-health.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-center-history.yml, .github/workflows/operational-center-html.yml, .github/workflows/operational-intelligence-hub.yml |
| `artifacts/operational-health/prs.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-center-history.yml, .github/workflows/operational-center-html.yml, .github/workflows/operational-intelligence-hub.yml |
| `artifacts/operational-health/runs.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-center-history.yml, .github/workflows/operational-center-html.yml, .github/workflows/operational-intelligence-hub.yml |
| `artifacts/operational-history/operational-history.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-drift-analyzer.yml, .github/workflows/operational-executive-dashboard.yml, .github/workflows/operational-governance-gate.yml, .github/workflows/operational-risk-engine.yml |
| `artifacts/operational-intelligence-hub/operational-intelligence-hub.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-center-history.yml, .github/workflows/operational-center-html.yml, .github/workflows/operational-executive-dashboard.yml, .github/workflows/operational-governance-gate.yml |
| `artifacts/operational-risk-engine/operational-risk-engine.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-drift-analyzer.yml, .github/workflows/operational-executive-dashboard.yml |
| `artifacts/ops-dashboard/data/health.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ops-dashboard.yml |
| `artifacts/pr-auto-recovery-controlled/execution-plan.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/pr-auto-recovery-controlled.yml |
| `artifacts/pr-auto-recovery/pr-auto-recovery.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/pr-auto-recovery-replacement-plan.yml |
| `artifacts/pr-auto-recovery/replacement-plan.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/pr-auto-recovery-replacement-plan.yml |
| `artifacts/pr-fast-classifier/classification.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/pr-fast-classifier.yml |
| `artifacts/prs.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/reqsys-operational-health.yml |
| `artifacts/repository-health-watchdog/repository-health-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ops-dashboard.yml |
| `artifacts/runs.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/reqsys-operational-health.yml |
| `artifacts/runtime-health-center/runtime-health-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/runtime-health-center.yml |
| `artifacts/runtime-risk-scoring/pr.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/runtime-risk-scoring.yml |
| `artifacts/runtime-risk-scoring/risk-score.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/runtime-risk-scoring.yml |
| `artifacts/runtime/ops-readiness-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/public-runtime-evidence.yml |
| `artifacts/runtime/public-runtime-validation.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/public-runtime-evidence.yml |
| `audit/runtime/ops-readiness-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/public-runtime-evidence.yml |
| `audit/runtime/public-runtime-evidence-index.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/public-runtime-evidence.yml |
| `audit/runtime/public-runtime-validation.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/public-runtime-evidence.yml |
| `audit/artifact-discovery/operational-artifact-discovery-index.json` | workflow | `docs/contracts/operational-artifact-discovery-index.schema.json` | .github/workflows/operational-artifact-discovery-index.yml |
| `audit/ci-lead-time-analytics.json` | workflow | `docs/contracts/ci-lead-time-analytics.schema.json` | .github/workflows/ci-lead-time-analytics.yml |
| `audit/command-center/command-center-readiness.json` | workflow | `docs/contracts/command-center-readiness.schema.json` | .github/workflows/command-center-readiness.yml |
| `audit/delivery-burndown/delivery-burndown-snapshot.json` | workflow | `docs/contracts/delivery-burndown-snapshot.schema.json` | .github/workflows/delivery-burndown-snapshot.yml, .github/workflows/delivery-evidence-report.yml |
| `audit/delivery-completion/delivery-completion-snapshot.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/delivery-completion-snapshot.yml |
| `audit/delivery-evidence/delivery-evidence-report.json` | workflow | `docs/contracts/delivery-evidence-report.schema.json` | .github/workflows/delivery-evidence-report.yml |
| `audit/delivery-readiness/delivery-readiness-report.json` | workflow | `docs/contracts/delivery-readiness-report.schema.json` | .github/workflows/delivery-readiness-report.yml |
| `audit/delivery/delivery-status-report.json` | workflow | `docs/contracts/delivery-status-report.schema.json` | .github/workflows/delivery-evidence-report.yml, .github/workflows/delivery-status-report.yml |
| `audit/extended-contract-validation/extended-operational-contract-validation.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/extended-operational-contract-validation.yml |
| `audit/history/operational-history-snapshot.json` | workflow | `docs/contracts/operational-history-snapshot.schema.json` | .github/workflows/operational-history-snapshot.yml |
| `audit/main-health/main-operational-post-merge-health.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/main-operational-post-merge-health.yml |
| `audit/main-post-merge-validation.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/main-post-merge-validation.yml |
| `audit/maturity/operational-maturity-score.json` | workflow | `docs/contracts/operational-maturity-score.schema.json` | .github/workflows/operational-maturity-score.yml |
| `audit/pr-evidence-gate.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/pr-evidence-gate.yml |
| `audit/predictive/runtime-predictive-analytics.json` | workflow | `docs/contracts/runtime-predictive-analytics.schema.json` | .github/workflows/runtime-predictive-analytics.yml |
| `audit/release-readiness/golden-release-readiness.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/golden-release-readiness.yml |
| `audit/scheduled-operational-watch.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/scheduled-operational-watch.yml |
| `audit/schema-validation/operational-artifact-schema-validation.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-artifact-schema-validation.yml |
| `auth-azure-operational-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/auth-azure-operational-gate.yml |
| `ci-lead-time-analytics.json` | workflow | `docs/contracts/ci-lead-time-analytics.schema.json` | .github/workflows/command-center-readiness.yml, .github/workflows/operational-artifact-discovery-index.yml |
| `config/ci-failure-knowledge-base.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-center-history.yml, .github/workflows/operational-center-html.yml, .github/workflows/operational-ci-intelligence.yml, .github/workflows/operational-intelligence-hub.yml |
| `config/failure-patterns.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/actions-deep-diagnostic.yml, .github/workflows/failure-pattern-engine.yml, .github/workflows/operational-center-history.yml, .github/workflows/operational-center-html.yml, .github/workflows/operational-intelligence-hub.yml |
| `config/pr-auto-recovery-gates.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/pr-auto-recovery-controlled.yml |
| `data/operational-history/history.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-center-history.yml |
| `data/operational/github-actions-history/runs.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/executive-predictive-stability.yml |
| `docs/arquitetura/config.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/ciclo-completo/estado-ciclo-reqsys.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/validar-painel-ciclo.yml |
| `docs/contracts/ci-lead-time-analytics.schema.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-artifact-discovery-index.yml, .github/workflows/operational-artifact-schema-validation.yml |
| `docs/contracts/delivery-burndown-snapshot.schema.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/delivery-evidence-report.yml |
| `docs/contracts/delivery-status-report.schema.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/delivery-evidence-report.yml |
| `docs/contracts/operational-artifact-discovery-index.schema.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/extended-operational-contract-validation.yml |
| `docs/contracts/operational-history-snapshot.schema.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-artifact-discovery-index.yml, .github/workflows/operational-artifact-schema-validation.yml |
| `docs/contracts/operational-maturity-score.schema.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/extended-operational-contract-validation.yml |
| `docs/contracts/release-readiness.schema.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/extended-operational-contract-validation.yml |
| `docs/contracts/runtime-predictive-analytics.schema.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-artifact-discovery-index.yml, .github/workflows/operational-artifact-schema-validation.yml |
| `docs/evidence/monitorador-apis-python-ci-stabilization-final-2.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/evidence/monitorador-apis-python-ci-stabilization-final-3.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/evidence/monitorador-apis-python-ci-stabilization-final-4.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/evidence/monitorador-apis-python-ci-stabilization-final-5.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/evidence/monitorador-apis-python-ci-stabilization-final-6.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/evidence/monitorador-apis-python-ci-stabilization-final-7.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/evidence/monitorador-apis-python-ci-stabilization-final.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/evidence/monitorador-apis-python-ci-stabilization-v2.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/evidence/monitorador-apis-python-ci-stabilization-v3.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/evidence/monitorador-apis-python-ci-stabilization.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/operations/operational-health-dashboard.example.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-health-dashboard.yml |
| `docs/operations/operational-health-dashboard.schema.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-health-dashboard.yml |
| `docs/ops-dashboard/data/health.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ops-dashboard.yml |
| `docs/product/product-intelligence-final-evidence-index.example.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/product/product-intelligence-final-evidence-index.schema.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/product/user-final-shell-contract.json` | docs | `docs/contracts/operational-json-artifact.schema.json` | - |
| `docs/schema-registry.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/schema-governance-gate.yml, .github/workflows/schema-runtime-validation.yaml |
| `drift-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ci-governance-drift-guard.yml |
| `evidence.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/manual-gate-guardrail.yml |
| `examples/product-intelligence/product-intelligence-event.example.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ai-assisted-product-decision-intelligence.yml, .github/workflows/functional-traceability-graph.yml, .github/workflows/product-intelligence-backlog-governance-gate.yml, .github/workflows/product-intelligence-backlog-publisher-governado.yml, .github/workflows/product-intelligence-consolidated-governance-report.yml, .github/workflows/product-intelligence-continuous-governance-snapshot.yml, .github/workflows/product-intelligence-event-validator.yml, .github/workflows/product-intelligence-evidence-navigation-artifact-publisher.yml, .github/workflows/product-intelligence-evidence-navigation-autonomous-governance-recovery-index.yml, .github/workflows/product-intelligence-evidence-navigation-compliance-drift-index.yml, .github/workflows/product-intelligence-evidence-navigation-governance-lifecycle-index.yml, .github/workflows/product-intelligence-evidence-navigation-retention-index.yml, .github/workflows/product-intelligence-evidence-navigation-ui.yml, .github/workflows/product-intelligence-executive-control-tower.yml, .github/workflows/product-intelligence-executive-release-board.yml, .github/workflows/product-intelligence-executive-summary-trendline.yml, .github/workflows/product-intelligence-final-evidence-index.yml, .github/workflows/product-intelligence-functional-roadmap-generator.yml, .github/workflows/product-intelligence-governance-closure-pack.yml, .github/workflows/product-intelligence-governance-drift-detector.yml, .github/workflows/product-intelligence-governance-stability-index.yml, .github/workflows/product-intelligence-governance-stabilization-gate.yml, .github/workflows/product-intelligence-release-evidence-pack.yml, .github/workflows/product-intelligence-release-governance-gate.yml, .github/workflows/product-intelligence-runtime-planning-package.yml, .github/workflows/product-intelligence-runtime-readiness-gate.yml, .github/workflows/reqsys-product-intelligence-dashboard.yml, .github/workflows/reqsys-product-intelligence-living-backlog.yml, .github/workflows/requirement-quality-scoring-engine.yml |
| `examples/runtime/product-intelligence-event.runtime.invalid-extra-field.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/schema-runtime-validation.yaml |
| `examples/runtime/product-intelligence-event.runtime.valid.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/schema-runtime-validation.yaml |
| `fly-auth-azure-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/configurar-fly-auth-azure.yml |
| `fly-enterprise-sync-validation.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/fly-enterprise-sync.yml |
| `frontend/package-lock.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ci-e2e.yml, .github/workflows/ci-enterprise-fast.yml, .github/workflows/ci-enterprise-regression.yml, .github/workflows/ci-security.yml, .github/workflows/ci.yml |
| `frontend/package.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ci-enterprise-fast.yml, .github/workflows/ci-enterprise-regression.yml |
| `golden-release-readiness.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/command-center-readiness.yml |
| `infra/fly-environments.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/fly-enterprise-sync.yml |
| `main-operational-post-merge-health.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-artifact-discovery-index.yml |
| `operational-alert-intelligence.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-alert-intelligence.yml |
| `operational-artifact-discovery-index.json` | workflow | `docs/contracts/operational-artifact-discovery-index.schema.json` | .github/workflows/command-center-readiness.yml |
| `operational-artifact-schema-validation.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-artifact-discovery-index.yml |
| `operational-event-stream.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-realtime-event-mesh.yml |
| `operational-history-snapshot.json` | workflow | `docs/contracts/operational-history-snapshot.schema.json` | .github/workflows/command-center-readiness.yml, .github/workflows/operational-artifact-discovery-index.yml |
| `operational-history.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/operational-data-lake-historical-intelligence.yml |
| `operational-maturity-score.json` | workflow | `docs/contracts/operational-maturity-score.schema.json` | .github/workflows/command-center-readiness.yml |
| `package-lock.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ci-enterprise-fast.yml, .github/workflows/ci-enterprise-regression.yml |
| `package-lock/.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/governed-dev-automerge.yml |
| `package.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/ci-enterprise-fast.yml, .github/workflows/ci-enterprise-regression.yml |
| `product-intelligence-evidence-navigation-artifact-manifest.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-artifact-publisher.yml |
| `product-intelligence-evidence-navigation-autonomous-governance-recovery-index.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-autonomous-governance-recovery-index.yml |
| `product-intelligence-evidence-navigation-compliance-drift-index.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-compliance-drift-index.yml |
| `product-intelligence-evidence-navigation-governance-lifecycle-index.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-governance-lifecycle-index.yml |
| `product-intelligence-evidence-navigation-retention-index.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-retention-index.yml |
| `product-intelligence-evidence-navigation-ui.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-ui.yml |
| `public-runtime-validation.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/fly-enterprise-sync.yml, .github/workflows/fly-runtime-p0.yml |
| `realtime-operational-feed.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/realtime-operational-streaming-layer.yml |
| `reports/github-runtime-analytics/runtime-operational-correlation-timeline.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/runtime-operational-correlation-timeline.yml |
| `reports/github-runtime-analytics/runtime-operational-evidence-graph.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/runtime-operational-evidence-graph.yml |
| `reports/product-intelligence/evidence-analytics-drilldown-runtime.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/evidence-analytics-drilldown-runtime.yml |
| `reports/product-intelligence/product-intelligence-evidence-navigation-artifact-manifest.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-artifact-publisher.yml |
| `reports/product-intelligence/product-intelligence-evidence-navigation-autonomous-governance-recovery-index.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-autonomous-governance-recovery-index.yml |
| `reports/product-intelligence/product-intelligence-evidence-navigation-compliance-drift-index.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-compliance-drift-index.yml |
| `reports/product-intelligence/product-intelligence-evidence-navigation-governance-lifecycle-index.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-governance-lifecycle-index.yml |
| `reports/product-intelligence/product-intelligence-evidence-navigation-retention-index.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-retention-index.yml |
| `reports/product-intelligence/product-intelligence-evidence-navigation-ui.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-evidence-navigation-artifact-publisher.yml |
| `reports/product-intelligence/product-intelligence-final-evidence-index.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/product-intelligence-final-evidence-index.yml |
| `reports/validacao-acessos-publicos.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/validacao-acessos.yml |
| `runs.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/post-merge-operational-summary.yml |
| `runtime-predictive-analytics.json` | workflow | `docs/contracts/runtime-predictive-analytics.schema.json` | .github/workflows/command-center-readiness.yml, .github/workflows/operational-artifact-discovery-index.yml |
| `schema-governance-report.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/schema-governance-gate.yml |
| `unified-operational-event.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/unified-operational-event-bus.yml |
| `}}.json` | workflow | `docs/contracts/operational-json-artifact.schema.json` | .github/workflows/configurar-fly-auth-azure.yml |
