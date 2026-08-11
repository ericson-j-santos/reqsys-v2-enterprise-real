# Enterprise Runtime Governance Gates

Status: **passed**

| Métrica | Valor |
|---|---:|
| Arquivos escaneados | 1523 |
| Bloqueios | 0 |
| Warnings | 78 |

| Severidade | Código | Arquivo | Linha | Mensagem |
|---|---|---|---:|---|
| MEDIUM | `SEC_HTTP_INSECURE` | `docker-compose.dotnet.yml` | 6 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `frontend-vuetify/index.html` | 9 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/testar_urls_ambiente.sh` | 9 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/testar_urls_ambiente.sh` | 10 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/testar_urls_ambiente.sh` | 11 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/reqsys_free_tier_backup.py` | 97 | URL HTTP insegura fora de localhost. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/pr_ci_watch.py` | 246 | Possível log de PII/segredo. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/workflow_command_center.py` | 293 | Possível log de PII/segredo. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/bootstrap_reqsys_r2_backup.py` | 122 | Possível log de PII/segredo. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/auto_rerun_governed.py` | 224 | Possível log de PII/segredo. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/runtime_production_smoke_governed.py` | 64 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/runtime_production_smoke_governed.py` | 65 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/build_bacen_backup_observability.py` | 303 | URL HTTP insegura fora de localhost. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/workflow_auto_remediation.py` | 183 | Possível log de PII/segredo. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/update_teams_v2_adaptive_card.py` | 119 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/validate_executive_promotion_advisor_comparative_public_smoke_trend_card.py` | 16 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/publicar_ambiente.sh` | 11 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/publicar_ambiente.sh` | 12 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/publicar_ambiente.sh` | 13 | URL HTTP insegura fora de localhost. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/actions_auto_operator.py` | 206 | Possível log de PII/segredo. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/trilha_e_arquitetura_viva.py` | 45 | URL HTTP insegura fora de localhost. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/coordenador_status_consolidator.py` | 980 | Possível log de PII/segredo. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/evaluate_github_workflow_token_readiness.py` | 52 | Possível log de PII/segredo. |
| MEDIUM | `SEC_SECRET_HARDCODED` | `scripts/executar-local.sh` | 89 | Possível segredo/token hardcoded. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/vault_setup.py` | 119 | Possível log de PII/segredo. |
| MEDIUM | `SEC_CONNECTION_STRING` | `scripts/verificar_movimento_email_fontes.py` | 79 | Possível connection string exposta. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/operational_governance_orchestrator.py` | 263 | Possível log de PII/segredo. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/smoke_executive_promotion_advisor_homologation_trend_public.py` | 34 | URL HTTP insegura fora de localhost. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/operational_analytics_engine.py` | 290 | Possível log de PII/segredo. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/notify_reqsys_logs_teams.py` | 332 | URL HTTP insegura fora de localhost. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/cutover_fly_postgres.py` | 178 | Possível log de PII/segredo. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/cutover_fly_postgres.py` | 223 | Possível log de PII/segredo. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/validate_public_runtime.py` | 49 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/validate_public_runtime.py` | 50 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/validate_executive_sync_stability_index_card.py` | 22 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/smoke_runtime_executive_public_endpoint.py` | 58 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/smoke_runtime_executive_public_endpoint.py` | 59 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/notify_hitl_approval_teams.py` | 122 | URL HTTP insegura fora de localhost. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/configurar_fly_auth_azure.py` | 175 | Possível log de PII/segredo. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/github_actions_history_lake.py` | 300 | Possível log de PII/segredo. |
| MEDIUM | `SEC_SECRET_HARDCODED` | `scripts/trigger_gitlab_pipeline.py` | 8 | Possível segredo/token hardcoded. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/validate_observability_e2e.py` | 48 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/validate_observability_e2e.py` | 49 | URL HTTP insegura fora de localhost. |
| MEDIUM | `LGPD_PII_LOGGING` | `scripts/evaluate_backup_provider_readiness.py` | 79 | Possível log de PII/segredo. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/smoke_executive_promotion_advisor_comparative_trend_public_sync.py` | 20 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `scripts/smoke_executive_promotion_advisor_comparative_trend_public_sync.py` | 27 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_CORS_WILDCARD` | `tools/validate_nginx_security.py` | 32 | Possível CORS wildcard. |
| MEDIUM | `LGPD_PII_LOGGING` | `.github/workflows/github-workflow-permission-readiness-watch.yml` | 165 | Possível log de PII/segredo. |
| MEDIUM | `SEC_SECRET_HARDCODED` | `.github/workflows/padrao-ouro-delivery-automation.yml` | 76 | Possível segredo/token hardcoded. |
| MEDIUM | `SEC_HTTP_INSECURE` | `.github/workflows/living-architecture-traceability.yml` | 95 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_SECRET_HARDCODED` | `.github/workflows/workflow-flakiness-inventory.yml` | 28 | Possível segredo/token hardcoded. |
| MEDIUM | `SEC_SECRET_HARDCODED` | `.github/workflows/required-checks-materialization-inventory.yml` | 30 | Possível segredo/token hardcoded. |
| MEDIUM | `SEC_SECRET_HARDCODED` | `.github/workflows/reqsys-backup-provider-readiness.yml` | 100 | Possível segredo/token hardcoded. |
| MEDIUM | `SEC_SECRET_HARDCODED` | `.github/workflows/reqsys-backup-provider-readiness.yml` | 123 | Possível segredo/token hardcoded. |
| MEDIUM | `SEC_HTTP_INSECURE` | `.github/workflows/teams-commit-notification.yml` | 164 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend-dotnet/src/ReqSys.Api/appsettings.json` | 8 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `services/environment-observability-api/compose.observability.dev.yml` | 7 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `services/environment-observability-api/compose.observability.dev.yml` | 38 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `services/environment-observability-api/observability/dev/grafana-provisioning/datasources/prometheus.yml` | 8 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `tools/geradores/gerar_servicos_email_teams.py` | 192 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `infra/reverse-proxy/scripts/linux-apache-apply.sh` | 75 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/services/automatic_diagram_server.py` | 155 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/services/automatic_diagram_server.py` | 156 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/services/automatic_diagram_server.py` | 157 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/services/automatic_diagram_server.py` | 158 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/services/teams_notification_solution_factory.py` | 251 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/services/teams_gateway.py` | 250 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/services/hub_lowcode.py` | 612 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/services/teams_status_cards.py` | 90 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/api/sistema.py` | 82 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/api/sistema.py` | 112 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/api/sistema.py` | 137 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/api/sistema.py` | 138 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/api/sistema.py` | 139 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/api/relatorios.py` | 73 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/api/dashboard.py` | 96 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/api/dashboard.py` | 97 | URL HTTP insegura fora de localhost. |
| MEDIUM | `SEC_HTTP_INSECURE` | `backend/app/core/config.py` | 40 | URL HTTP insegura fora de localhost. |
