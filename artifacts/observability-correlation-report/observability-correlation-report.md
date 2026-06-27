# Observability Correlation Report

- Modo: `report-only`
- Branch: `work`
- Commit: `abac13d12e95c76c184f06d540460456e458f465`
- Fontes mapeadas: `545`
- Artifacts mapeados: `4`
- Risco operacional: `low`
- Confiança: `high`

## Cobertura

- `runtime_health`: 325
- `delivery_evidence`: 466
- `readiness`: 197
- `completion`: 242
- `burndown`: 72

## Correlações

| Tipo | Caminho/artifact | Categorias | Status | Run | SHA | Branch | PR | Risco | Confiança |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| workflow | `.github/workflows/actions-auto-operator.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/actions-deep-diagnostic.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/actions-dispatcher.yml` | completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ai-assisted-product-decision-intelligence.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/auth-azure-operational-gate.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/auto-public-runtime-evidence.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/auto-rerun-governed.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/branch-protection-audit.yml` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ci-e2e.yml` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ci-enterprise-fast.yml` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ci-enterprise-regression.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ci-fast-operational.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ci-governance-drift-guard.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ci-incident-intelligence.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ci-lead-time-analytics.yml` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ci-observability.yml` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ci-runtime-health-summary.yml` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ci-security.yml` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ci.yml` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/codex-local-online.yml` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/command-center-readiness.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/configurar-fly-auth-azure.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/deep-governance-review.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/delivery-burndown-snapshot.yml` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/delivery-completion-snapshot.yml` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/delivery-evidence-report.yml` | runtime_health, delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/delivery-readiness-report.yml` | delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/delivery-status-report.yml` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/deploy-reqsys-showcase-pages.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/dispatch-public-runtime-evidence.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/enterprise-runtime-governance-gates.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/evidence-analytics-drilldown-runtime.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/executive-predictive-stability.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/extended-operational-contract-validation.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/failure-pattern-engine.yml` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/fly-enterprise-sync.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/fly-governed-command-center.yml` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/fly-runtime-p0.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/functional-traceability-graph.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/github-runtime-analytics.yml` | runtime_health | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/golden-release-readiness.yml` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/governanca-padrao-ouro.yml` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/governance-quality-gates.yml` | readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/governed-auto-remediation-engine.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/governed-dev-automerge.yml` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/governed-pr-automation.yml` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/governed-promotion-pipeline.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/live-operational-control-center.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/main-operational-health.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/main-operational-post-merge-health.yml` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/main-post-merge-validation.yml` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/main-smoke-ci.yml` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/manual-gate-guardrail.yml` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-alert-intelligence.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-analytics-engine.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-artifact-discovery-index.yml` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-artifact-schema-validation.yml` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-center-history.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-center-html.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-ci-intelligence.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-data-lake-historical-intelligence.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-drift-analyzer.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-executive-dashboard-generator.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-executive-dashboard.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-governance-gate.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-governance-orchestrator.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-health-dashboard.yml` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-history-snapshot.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-intelligence-hub.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-maturity-score.yml` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-realtime-event-mesh.yml` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-risk-engine.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/operational-stability-score.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/ops-dashboard.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/post-merge-operational-summary.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/pr-auto-recovery-controlled.yml` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/pr-auto-recovery-replacement-plan.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/pr-auto-recovery.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/pr-ci-watch.yml` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/pr-conflict-guard.yml` | readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/pr-evidence-gate.yml` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/pr-fast-classifier.yml` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/pr-governed-ci-self-check.yml` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/pr-governed-ci-validation.yml` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/pr-quality-review.yml` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/pr-scope-labeler.yml` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-backlog-governance-gate.yml` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-backlog-publisher-governado.yml` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-consolidated-governance-report.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-continuous-governance-snapshot.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-event-validator.yml` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-evidence-navigation-artifact-publisher.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-evidence-navigation-autonomous-governance-recovery-index.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-evidence-navigation-compliance-drift-index.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-evidence-navigation-governance-lifecycle-index.yml` | runtime_health, delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-evidence-navigation-recovery-execution-readiness-gate.yml` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-evidence-navigation-retention-index.yml` | runtime_health, delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-evidence-navigation-ui.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-executive-control-tower.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-executive-release-board.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-executive-summary-trendline.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-final-evidence-index.yml` | runtime_health, delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-functional-roadmap-generator.yml` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-governance-closure-pack.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-governance-drift-detector.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-governance-stability-index.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-governance-stabilization-gate.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-release-evidence-pack.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-release-governance-gate.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-runtime-planning-package.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/product-intelligence-runtime-readiness-gate.yml` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/public-runtime-evidence.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/realtime-operational-mesh.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/realtime-operational-streaming-layer.yml` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/repository-health-watchdog.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/reqsys-operational-health.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/reqsys-product-intelligence-dashboard.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/reqsys-product-intelligence-living-backlog.yml` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/requirement-quality-scoring-engine.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/runtime-health-center.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/runtime-health-validator.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/runtime-operational-correlation-timeline.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/runtime-operational-evidence-graph.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/runtime-operational-health.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/runtime-predictive-analytics.yml` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/runtime-risk-scoring.yml` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/scheduled-operational-watch.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/schema-governance-gate.yml` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/schema-runtime-validation.yaml` | runtime_health, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/stale-pr-governance-watch.yml` | completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/testes-monitorador-apis-python.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/unified-operational-event-bus.yml` | runtime_health, completion | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/validacao-acessos.yml` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/validar-painel-ciclo.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/workflow-auto-remediation.yml` | delivery_evidence | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/workflow-command-center.yml` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| workflow | `.github/workflows/workflow-reliability-analytics.yml` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/00_INDICE_CANONICO.md` | runtime_health, delivery_evidence, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/01_REQSYS_REFERENCIA_CONSOLIDADA.md` | delivery_evidence, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ADR/ADR-0001-padrao-ouro-enterprise.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/COFRE_UNIFICACOES_DASHBOARD_REQSYS.md` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ENDPOINTS_VERIFICATION_SUMMARY.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ENDPOINT_TESTING.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/FAILURE_PATTERN_ENGINE_P01.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/GITFLOW.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/IMPLEMENTATION_COMPLETE.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/OPERATIONAL_CENTER_HISTORY_P0.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/OPERATIONAL_CENTER_HTML_P0.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/OPERATIONAL_CI_INTELLIGENCE_P0.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/OPERATIONAL_INTELLIGENCE_HUB_P0.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/PADRAO_OURO_FLYIO_DUCKDNS.md` | runtime_health, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/POST_MERGE_CI_FIX_2026_06_23.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/PR18_POST_MERGE_EVIDENCE.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/REGISTRO_MUDANCA_DOMINIOS_2026-05-01.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/REQSYS_PADRAO_OURO_TRANSVERSAL.md` | delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/REQSYS_RUNTIME_PLATFORM_P0.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/RUNBOOK_PUBLICACAO_1PAGINA.md` | runtime_health, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/SECURITY_GATES_TEST_MATRIX.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/SUMMARY_IMPLEMENTATION.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/VALIDACAO_ANALITICA_ACESSOS.md` | runtime_health, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-0002-seguranca-gates-producao.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-0003-ambientes-dev-hml-prod.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-0004-ci-cd-qualidade.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-0005-observabilidade-auditoria.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-0021-coderabbit-fast-review-governance.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-0024-substituicao-coderabbit-pr-quality-review.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-0024-validation-note.md` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-020-connection-broker-permission-on-demand.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-021-figma-github-retorno-em-tela.md` | readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-022-autonomous-operations-platform-p0-1.md` | runtime_health, delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-023-aop-runtime-health-validator-remediation-executor.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-030-governed-dev-automerge.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-031-runtime-risk-and-promotion-pipeline.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-032-operational-health-dashboard-governance.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-033-product-intelligence-final-evidence-index.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-034-autonomous-operational-runtime-consolidation.md` | runtime_health, delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-ESTATISTICAS-INTERNAS-EXTERNAS.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-PR-AUTO-RECOVERY-V2.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-PR-AUTO-RECOVERY-V3.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-REQSYS-OPER-005-monitoramento-operacional.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adr/ADR-USER-FINAL-SHELL-001.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adrs/ADR-023-codex-backend-governado.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adrs/ADR-023-nginx-secure-profile.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adrs/ADR-024-ci-router-trunk-based.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/adrs/ADR-024-codex-operational-audit-layer.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/agile-multi-ia-sprint-router.md` | runtime_health, delivery_evidence, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/agile-runtime-core.md` | runtime_health, delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/agile-runtime-workflow.md` | runtime_health, delivery_evidence, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ai-governance/00-CORE/AI_EXECUTION_POLICY.md` | burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ai-governance/00-CORE/AI_SYSTEM_RULES.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ai-governance/00_PRIORITY_RULES.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ai-governance/01-ARQUITETURA/LIVING_ARCHITECTURE.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ai-governance/02-SEGURANCA/SECURITY_BASELINE.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ai-governance/03-FRONTEND/ANALYTICS_DRILLDOWN.md` | burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ai-governance/08-IA/AGENT_GOVERNANCE.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ai-governance/08-IA/MULTIAGENT_STANDARD.md` | burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ai-governance/09-CHECKLISTS/PADRAO_OURO.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/analytics/ANALYTICS_DRILLDOWN_PADRAO.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/api/connection-broker-runtime-contract.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/architecture/adr/ADR-025-operational-actions-center.md` | runtime_health, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/architecture/live-operational-dashboard-foundation.md` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/architecture/runtime-correlation-graph.md` | runtime_health, delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/audit/pr145-clean-replacement-audit.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/auth/AZURE_AD_LOGIN_OPERACIONAL.md` | readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/auth/WORKFLOW_CONFIGURAR_FLY_AUTH_AZURE.md` | readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/changelog/monitorador-apis-python-ci-stabilization.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/changelog/pr-auto-recovery-v3-controlled.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/changelog/user-final-shell-visual-v1.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/AUTONOMOUS_OPERATIONAL_RUNTIME.md` | runtime_health, delivery_evidence, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/CI_ACCELERATION_STRATEGY.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/GOVERNED_DEV_AUTOMERGE.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/PR_AUTO_RECOVERY_V3_VALIDATION.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/PR_GOVERNED_CI_VALIDATION_FIX.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/RAG_PYTHON_PR143_CI_REVALIDATION.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/RUNTIME_RISK_AND_PROMOTION_PIPELINE.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/WORKFLOW_STABILITY_EXECUTION_PLAN.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/WORKFLOW_STABILITY_VALIDATION.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/monitorador-apis-python-ci-stabilization.md` | runtime_health, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/monitorador-apis-python-coverage-fix-extra.md` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/monitorador-apis-python-coverage-fix-validation.md` | readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/monitorador-apis-python-coverage-fix.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/monitorador-apis-python-post-merge-incident.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/monitorador-apis-python-safe-decision.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/monitorador-apis-python-safe-fix-summary.md` | runtime_health, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr-quality-review-artifact-contract.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr-quality-review-decision.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr-quality-review-faq.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr-quality-review-flow.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr-quality-review-index.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr-quality-review-manual-gates.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr-quality-review-rollout.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr145-clean-replacement-summary.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr145-replacement-acceptance.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr145-replacement-dod.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr145-replacement-final-note.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr145-replacement-risk.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr145-replacement-rollback.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr145-replacement-status.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr145-replacement-summary-final.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ci/pr145-replacement-trace.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ciclo-completo/ADR-REQSYS-CYCLE-TRACKER.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ciclo-completo/CHANGELOG.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ciclo-completo/README.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ciclo-completo/RUNBOOK_VERSIONAMENTO.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ciclo-completo/TEST_REPORT.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ciclo-completo/estado-ciclo-reqsys.json` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/codex-local/DECISAO_MODELOS_CODIFICACAO.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/codex-local/RUNBOOK_PUBLICAR_REPOSITORIO_OLLAMA_GATEWAY.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/ci-lead-time-analytics.schema.json` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/command-center-readiness.schema.json` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/contract-validation-report.schema.json` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/delivery-burndown-snapshot.schema.json` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/delivery-evidence-report.schema.json` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/delivery-readiness-report.schema.json` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/delivery-status-report.schema.json` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/observability-correlation-report.schema.json` | runtime_health, delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/operational-artifact-discovery-index.schema.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/operational-history-index.schema.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/operational-history-snapshot.schema.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/operational-maturity-score.schema.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/release-readiness.schema.json` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/contracts/runtime-predictive-analytics.schema.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/dashboard/command-center-evidence-index.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/dashboard/command-center-navigation-map.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/dashboard/live-operational-dashboard.dynamic.html` | runtime_health, delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/dashboard/live-operational-dashboard.html` | runtime_health, delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/dashboard/operational-command-center.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/devops/PLANO_EVOLUTIVO_DEVOPS_CORPORATIVO.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/diagrama-dependencias.md` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/github-runtime-analytics.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/monitorador-apis-python-ci-stabilization-final-2.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/monitorador-apis-python-ci-stabilization-final-3.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/monitorador-apis-python-ci-stabilization-final-4.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/monitorador-apis-python-ci-stabilization-final-5.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/monitorador-apis-python-ci-stabilization-final-6.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/monitorador-apis-python-ci-stabilization-final-7.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/monitorador-apis-python-ci-stabilization-final.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/monitorador-apis-python-ci-stabilization-v2.json` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/monitorador-apis-python-ci-stabilization-v3.json` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/monitorador-apis-python-ci-stabilization.json` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/monitorador-apis-python-ci-stabilization.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/operational-health-dashboard-governance.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/pr-quality-review-validation.md` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/pr145-clean-replacement-evidence.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/pr145-clean-replacement-links.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidence/pr225-evidence-navigation-ui-sync.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidencias/PR7_READINESS_PADRAO_OURO.md` | runtime_health, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/evidencias-operacionais/templates/auth-azure-login-evidence.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/governanca/CONNECTION_BROKER_PERMISSION_ON_DEMAND.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/governanca/PADRAO_OURO_ENTERPRISE.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/governance/CODERABBIT_FAST_REVIEW_GUARDRAILS.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/governance/branch-protection-enterprise-baseline.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/governance/enterprise-runtime-governance-gates.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/governance/governance-quality-gates-fix.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/governance/pr-quality-review-policy.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/index.html` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/monitorador-apis-python/index.html` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/monitoramento-operacional/connection-broker-dashboard.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/monitoramento-operacional-reqsys.md` | delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/observabilidade/OBSERVABILIDADE_PADRAO.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ollama-local-gateway/BOOTSTRAP_REPOSITORY.md` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ollama-local-gateway/bootstrap-files/README.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ollama-local-gateway/bootstrap-files/SECURITY.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ollama-local-gateway/bootstrap-files/src/reqsys_ollama_gateway/app.py` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ollama-local-gateway/bootstrap-files/src/reqsys_ollama_gateway/config.py` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ollama-local-gateway/bootstrap-files/tests/test_health.py` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operacao/fly-enterprise-sync.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operacional/email-mime-html-report-v1.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operational-runtime-governance-platform/README.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operational-runtime-governance-platform/relatorio-operational-runtime-governance-platform-v1.html` | runtime_health, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/GITHUB_RUNTIME_ANALYTICS.md` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/OPERATIONAL_HEALTH_DASHBOARD.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/RUNTIME_OPERATIONAL_CORRELATION_TIMELINE.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/RUNTIME_OPERATIONAL_EVIDENCE_GRAPH.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/ci-evidence-refresh-2026-06-25.md` | runtime_health, delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/ci-incident-intelligence.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/governed-auto-remediation-engine.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/live-operational-control-center.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/operational-alert-intelligence.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/operational-data-lake-historical-intelligence.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/operational-executive-dashboard-generator.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/operational-health-dashboard.example.json` | runtime_health, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/operational-health-dashboard.schema.json` | runtime_health, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/operational-stability-score.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/post-merge-operational-summary.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/realtime-operational-mesh.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/realtime-operational-streaming-layer.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/runtime-ops-governance-p1.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/unified-operational-event-bus.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/operations/workflow-reliability-analytics.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ops/pr-quality-review-operational-status.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ops/pr145-clean-replacement-next-steps.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ops-dashboard/data/health.json` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/ops-dashboard/index.html` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/painel-ciclo-completo-reqsys.html` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/pipeline-governanca.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product/PRODUCT_INTELLIGENCE_FINAL_EVIDENCE_INDEX.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product/product-intelligence-final-evidence-index.example.json` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product/product-intelligence-final-evidence-index.schema.json` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product/user-final-shell-contract.json` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/EVIDENCE_NAVIGATION_ARTIFACT_PUBLISHER.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/EVIDENCE_NAVIGATION_AUTONOMOUS_GOVERNANCE_RECOVERY_INDEX.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/EVIDENCE_NAVIGATION_COMPLIANCE_DRIFT_INDEX.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/EVIDENCE_NAVIGATION_GOVERNANCE_LIFECYCLE_INDEX.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/EVIDENCE_NAVIGATION_RECOVERY_EXECUTION_READINESS_GATE.md` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/EVIDENCE_NAVIGATION_RETENTION_INDEX.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/EVIDENCE_NAVIGATION_UI.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/FINAL_EVIDENCE_INDEX_PLAN.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/PR225_SUPERSEDED_BY_MAIN.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/ai-assisted-product-decision-intelligence.md` | runtime_health, delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/evidence-navigation-ui.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/functional-traceability-graph.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-backlog-governance-gate.md` | runtime_health, delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-backlog-publisher-governado.md` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-consolidated-governance-report.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-continuous-governance-snapshot.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-event-model.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-event-validator.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-executive-control-tower.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-executive-release-board.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-executive-summary-trendline.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-functional-roadmap-generator.md` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-governance-closure-pack.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-governance-drift-detector.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-governance-stability-index.md` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-governance-stabilization-gate.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-release-evidence-pack.md` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-release-governance-gate.md` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-runtime-planning-package.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/product-intelligence-runtime-readiness-gate.md` | runtime_health, readiness, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/reqsys-product-intelligence-dashboard.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/reqsys-product-intelligence-living-backlog.md` | runtime_health, delivery_evidence, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/product-intelligence/requirement-quality-scoring-engine.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/public-showcase/GITHUB_PAGES_FIX.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/public-showcase/post-linkedin-url.md` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/public-showcase/reqsys-linkedin/index.html` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/public-showcase/roteiro-carrossel-linkedin.md` | runtime_health, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/publicacao/PUBLICACAO_GOVERNANCA_PORTAL_2026-06-20.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/quality/pr-quality-review-checklist.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/relatorios/email-relatorio-operacional-visual-v1.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/release-notes/pr145-clean-replacement.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/2026-06-18-pr18-production-security-gates.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/2026-06-18-req021-validacao-acessos-main.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/2026-06-20-coderabbit-config-governanca-evidencia.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/2026-06-20-coderabbit-config-governanca.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/2026-06-20-monitoramento-operacional-reqsys.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/2026-06-20-pr35-revalidacao-ci.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/2026-06-20-reqsys-oper-004-pipeline-governanca.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/2026-06-20-reqsys-oper-005-monitoramento-operacional-v2.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/2026-06-20-reqsys-oper-005-ready-for-pr.md` | readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/RELEASE-AOP-P0-1-operacao-autonoma.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/RELEASE-AOP-P0-2-runtime-health-remediation.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/ci-router-v1.0.0.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/codex-backend-governado-v1.1.0.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/codex-local-online-v1.0.0.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/codex-operational-audit-p1.2.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/governed-dev-automerge-v0.1.0.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/governed-pr-automation-v1.0.0.md` | runtime_health, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/operational-actions-center-v1.0.0.md` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/pr-ci-watch-v1.0.0.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/releases/runtime-risk-promotion-pipeline-v0.1.0.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/reports/monitorador-apis-python-ci-stabilization-compact.html` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/reports/monitorador-apis-python-ci-stabilization.html` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/reports/nginx-secure-profile.html` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/RUNBOOK-aop-operacao-autonoma-p0-1.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/RUNBOOK-aop-p0-2-runtime-health-remediation.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/actions-auto-operator.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/auto-public-runtime-evidence.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/ci-fast-deep-review.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/ci-lead-time-analytics.md` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/ci-lead-time-kpi-contract.md` | delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/ci-router.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/codex-local-online.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/codex-operational-audit-layer.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/delivery-burndown-snapshot.md` | runtime_health, delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/delivery-evidence-index.md` | runtime_health, delivery_evidence, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/delivery-status-report.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/executive-predictive-stability-ci.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/executive-predictive-stability-layer.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/fly-governed-command-center.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/fly-runtime-p0.md` | runtime_health, delivery_evidence, readiness, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/github-actions-history-lake.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/github-runtime-analytics.md` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/golden-release-operational-checklist.md` | runtime_health, delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/governed-operational-history-storage.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/governed-pr-automation.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/main-operational-health.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/main-operational-post-merge-health.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/main-post-merge-validation.md` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/main-smoke-ci.md` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/manual-gate-guardrail.md` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/monitorador-apis-python-ci.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/nginx-secure-profile.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/observability-correlation-report.md` | runtime_health, delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/operational-actions-center.md` | runtime_health, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/operational-analytics-engine.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/operational-analytics-persistence-v1.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/operational-artifact-discovery-index.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/operational-artifact-schema-validation.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/operational-burndown-executive.md` | runtime_health, delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/operational-governance-dashboard.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/operational-governance-orchestrator.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/operational-health-dashboard.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/operational-history-snapshots.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/ops-dashboard.md` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/post-merge-operational-maturity-matrix.md` | runtime_health, delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/pr-auto-recovery-pipeline.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/pr-auto-recovery-replacement-plan.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/pr-auto-recovery-v2-assisted.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/pr-auto-recovery-v3-controlled.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/pr-auto-recovery-v4-controlled-dispatch.md` | delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/pr-ci-watch.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/pr-evidence-gate.md` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/pr-quality-review.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/pr145-conflict-resolution.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/product-intelligence-final-evidence-index.md` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/public-runtime-evidence-gate.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/public-runtime-smoke-test.md` | runtime_health, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/rag-python-llamaindex-governado.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/repository-health-watchdog.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/reqsys-verificacao-real-antes-de-pronto.md` | completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/runtime-correlation-analytics-foundation.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/runtime-dashboard-schema-v1.md` | runtime_health, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/runtime-evidence-analytics.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/runtime-evidence-ingestion-contract.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/runtime-health-validator.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/runtime-operational-health.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/runtime-operational-observability-v1.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/runtime-predictive-analytics.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/runtime-public-access-readiness.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/runtime-public-json-contracts.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/workflow-auto-remediation.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/runbooks/workflow-command-center.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/schema-governance-gates.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/schema-registry.json` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/schema-runtime-enforcement.md` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/sdd-dashboard.html` | readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/ADR_LINKS.md` | burndown | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/APPROVAL_GATE.md` | readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/CHANGELOG.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/CHANGE_CONTROL.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/CI_EXPECTATIONS.md` | readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/DATA_GOVERNANCE.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/DECISION_LOG.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/EXECUTION_SUMMARY.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/FINAL_PRE_PR_CHECK.md` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/IMPLEMENTATION_NOTES.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/INTEGRATION_CHECKLIST.md` | readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/KNOWN_LIMITATIONS.md` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/MERGE_POLICY.md` | delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/NEXT_INCREMENT.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/PR_BODY.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/PR_READY_NOTE.md` | readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/PULL_REQUEST_SUMMARY.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/README.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/RELEASE_NOTE.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/REQSYS_STATISTICS_TAB_SPEC.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/RISK_REGISTER.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/STATUS.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/TRACEABILITY_MATRIX.md` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/V2_IMPLEMENTATION.md` | runtime_health | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/V2_RELEASE_NOTE.md` | runtime_health, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/V2_TEST_PLAN.md` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/statistics/VALIDATION_REPORT.md` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/strategy/REQSYS_ATUALIZACAO_CONSOLIDADA_2026-06-26.md` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| dashboard_or_doc | `docs/varreduras/REQSYS_VARREDURA_PADRAO_OURO_2026-06-20.md` | delivery_evidence | mapped |  |  |  |  | low | medium |
| script | `scripts/actions_auto_operator.py` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/auto_rerun_governed.py` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/ci_enterprise_guardrails.py` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| script | `scripts/configurar_fly_auth_azure.py` | runtime_health, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/executive_predictive_stability_layer.py` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/failure_pattern_engine.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/generate_ops_dashboard_data.py` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| script | `scripts/github_actions_deep_diagnostic.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/github_actions_history_lake.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/governance/enterprise_runtime_governance_gates.py` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| script | `scripts/observability_correlation_report.py` | runtime_health, delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| script | `scripts/operational_analytics_engine.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/operational_center_html.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/operational_ci_intelligence.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/operational_drift_analyzer.py` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| script | `scripts/operational_executive_dashboard.py` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| script | `scripts/operational_governance_dashboard.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/operational_governance_gate.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/operational_governance_orchestrator.py` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/operational_history.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/operational_intelligence_hub.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/operational_risk_engine.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/pr_auto_recovery.py` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/pr_auto_recovery_replacement_plan.py` | delivery_evidence | mapped |  |  |  |  | low | medium |
| script | `scripts/pr_ci_watch.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/pr_quality_review.py` | runtime_health, delivery_evidence | mapped |  |  |  |  | low | medium |
| script | `scripts/repository_health_watchdog.py` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/reqsys_operational_health.py` | runtime_health, delivery_evidence, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/runtime_health_center.py` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| script | `scripts/runtime_health_validator.py` | runtime_health, delivery_evidence, readiness, completion, burndown | mapped |  |  |  |  | low | medium |
| script | `scripts/validar-acessos-publicos.mjs` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| script | `scripts/validar-pipeline-governanca.mjs` | delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| script | `scripts/validar_login_azure_operacional.py` | runtime_health, readiness | mapped |  |  |  |  | low | medium |
| script | `scripts/validate_fly_enterprise_sync.py` | runtime_health, readiness | mapped |  |  |  |  | low | medium |
| script | `scripts/validate_fly_runtime_config.py` | runtime_health, readiness, burndown | mapped |  |  |  |  | low | medium |
| script | `scripts/validate_public_runtime.py` | runtime_health, delivery_evidence, readiness | mapped |  |  |  |  | low | medium |
| script | `scripts/vault_setup.py` | runtime_health | mapped |  |  |  |  | low | medium |
| script | `scripts/workflow_auto_remediation.py` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| script | `scripts/workflow_command_center.py` | runtime_health, delivery_evidence, readiness, completion | mapped |  |  |  |  | low | medium |
| artifact | `examples` | delivery_evidence, completion | available |  |  |  | 129 | medium | low |
| artifact | `examples` | delivery_evidence, completion | available |  |  |  | 129 | medium | low |
| artifact | `public-access-validation` | runtime_health, delivery_evidence, readiness | available |  |  |  | 323 | medium | low |
| artifact | `runtime-health-center` | runtime_health, delivery_evidence, readiness | available |  |  |  |  | high | low |
