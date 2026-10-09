# Auditoria local do runtime Docker

- Gerado em UTC: 2026-10-07T10:32:17.5450769Z
- Janela de coleta UTC: 2026-10-07T10:30:16.0262858Z a 2026-10-07T10:32:17.5450769Z
- Logs: contagens em janelas moveis de 30 minutos observadas durante a coleta
- Escopo: estacao local; hostname, username e caminhos absolutos redigidos
- Caminhos locais: aliases estaveis no formato <LOCAL_PATH:hash>/nome
- Containers: 69 total; 17 ativos; 0 reiniciando; 0 ativos unhealthy
- Ativos sem limites de recurso: 17; sem rotacao json-file: 17; com Compose ausente: 7
- Binds: 10 origens ausentes; 3 incompatibilidades de tipo
- Achados: 2 criticos; 70 altos

| Severidade | Container | Projeto | Estado | Codigo | Detalhe |
| --- | --- | --- | --- | --- | --- |
| critical | reqsys-dev-failover-tunnel |  | running | cloudflare-tunnel-not-found | matches_30m=118 |
| critical | reqsys-dev-gateway-tunnel |  | running | cloudflare-tunnel-not-found | matches_30m=108 |
| high | console_seguro_bundle_compose-app-1 | console_seguro_bundle_compose | exited | missing-compose-file | <LOCAL_PATH:4cb5e2f2565f>/docker-compose.yml |
| high | console_seguro_bundle_compose-appdb-1 | console_seguro_bundle_compose | exited | missing-bind-source | source=<LOCAL_PATH:de9be3267dc9>/appdb; destination=/docker-entrypoint-initdb.d; expected=unspecified; actual=missing |
| high | console_seguro_bundle_compose-appdb-1 | console_seguro_bundle_compose | exited | missing-compose-file | <LOCAL_PATH:4cb5e2f2565f>/docker-compose.yml |
| high | console_seguro_bundle_compose-grafana-1 | console_seguro_bundle_compose | exited | missing-bind-source | source=<LOCAL_PATH:a67bbf56af64>/dashboard.json; destination=/var/lib/grafana/dashboards/dashboard.json; expected=file; actual=missing |
| high | console_seguro_bundle_compose-grafana-1 | console_seguro_bundle_compose | exited | missing-bind-source | source=<LOCAL_PATH:899520fab74a>/datasources; destination=/etc/grafana/provisioning/datasources; expected=unspecified; actual=missing |
| high | console_seguro_bundle_compose-grafana-1 | console_seguro_bundle_compose | exited | missing-bind-source | source=<LOCAL_PATH:d859d47146bb>/dashboards; destination=/etc/grafana/provisioning/dashboards; expected=unspecified; actual=missing |
| high | console_seguro_bundle_compose-grafana-1 | console_seguro_bundle_compose | exited | missing-compose-file | <LOCAL_PATH:4cb5e2f2565f>/docker-compose.yml |
| high | console_seguro_bundle_compose-nginx-1 | console_seguro_bundle_compose | exited | missing-compose-file | <LOCAL_PATH:4cb5e2f2565f>/docker-compose.yml |
| high | console_seguro_bundle_compose-prometheus-1 | console_seguro_bundle_compose | exited | missing-bind-source | source=<LOCAL_PATH:cf622b217bec>/prometheus.yml; destination=/etc/prometheus/prometheus.yml; expected=file; actual=missing |
| high | console_seguro_bundle_compose-prometheus-1 | console_seguro_bundle_compose | exited | missing-compose-file | <LOCAL_PATH:4cb5e2f2565f>/docker-compose.yml |
| high | console_seguro_bundle_compose-rodb-1 | console_seguro_bundle_compose | exited | missing-bind-source | source=<LOCAL_PATH:6303f122bf32>/init_rodb; destination=/docker-entrypoint-initdb.d; expected=unspecified; actual=missing |
| high | console_seguro_bundle_compose-rodb-1 | console_seguro_bundle_compose | exited | missing-compose-file | <LOCAL_PATH:4cb5e2f2565f>/docker-compose.yml |
| high | cpf_suite_monorepo_v1_1_0-api-1 | cpf_suite_monorepo_v1_1_0 | exited | missing-compose-file | <LOCAL_PATH:8d1aee14b9de>/docker-compose.yml |
| high | cpf_suite_monorepo_v1_1_0-front-1 | cpf_suite_monorepo_v1_1_0 | exited | missing-compose-file | <LOCAL_PATH:8d1aee14b9de>/docker-compose.yml |
| high | cpf_suite_monorepo_v1_1_0-worker-1 | cpf_suite_monorepo_v1_1_0 | exited | missing-compose-file | <LOCAL_PATH:8d1aee14b9de>/docker-compose.yml |
| high | db-stack-docker-api-1 | db-stack-docker | exited | missing-compose-file | <LOCAL_PATH:1a43f4d11aca>/docker-compose.yml |
| high | db-stack-docker-web-1 | db-stack-docker | exited | missing-bind-source | source=<LOCAL_PATH:30fb9bcb37d5>/certs; destination=/etc/nginx/certs; expected=unspecified; actual=missing |
| high | db-stack-docker-web-1 | db-stack-docker | exited | missing-compose-file | <LOCAL_PATH:1a43f4d11aca>/docker-compose.yml |
| high | github-main-api-1 | github-main | exited | missing-compose-file | <LOCAL_PATH:a6c120120ab8>/docker-compose.kb-host.yml |
| high | github-main-api-1 | github-main | exited | unhealthy | state=exited; health=unhealthy |
| high | github-main-db-1 | github-main | exited | missing-compose-file | <LOCAL_PATH:a6c120120ab8>/docker-compose.kb-host.yml |
| high | github-main-db-1 | github-main | exited | unhealthy | state=exited; health=unhealthy |
| high | github-main-frontend-1 | github-main | exited | missing-compose-file | <LOCAL_PATH:a6c120120ab8>/docker-compose.kb-host.yml |
| high | github-main-kb-1 | github-main | exited | missing-compose-file | <LOCAL_PATH:a6c120120ab8>/docker-compose.kb-host.yml |
| high | github-main-nginx-1 | github-main | created | missing-compose-file | <LOCAL_PATH:a6c120120ab8>/docker-compose.kb-host.yml |
| high | egovhub-backend | infra | exited | missing-compose-file | <LOCAL_PATH:67b68fa170be>/docker-compose.yml |
| high | egovhub-frontend | infra | exited | missing-compose-file | <LOCAL_PATH:67b68fa170be>/docker-compose.yml |
| high | infra-postgres-1 | infra | exited | missing-compose-file | <LOCAL_PATH:138f8b4e2af8>/docker-compose.yml |
| high | infra-rabbitmq-1 | infra | exited | missing-compose-file | <LOCAL_PATH:138f8b4e2af8>/docker-compose.yml |
| high | infra-redis-1 | infra | exited | missing-compose-file | <LOCAL_PATH:138f8b4e2af8>/docker-compose.yml |
| high | infra-worker-1 | infra | exited | missing-compose-file | <LOCAL_PATH:138f8b4e2af8>/docker-compose.yml |
| high | mvp_intelligence-api-1 | mvp_intelligence | exited | missing-bind-source | source=<LOCAL_PATH:e7d2d10f34b3>/mvp_intelligence; destination=/app; expected=unspecified; actual=missing |
| high | mvp_intelligence-api-1 | mvp_intelligence | exited | missing-compose-file | <LOCAL_PATH:61328094fd45>/docker-compose.yml |
| high | mvp_intelligence-sqlserver-1 | mvp_intelligence | exited | missing-compose-file | <LOCAL_PATH:61328094fd45>/docker-compose.yml |
| high | mvp_intelligence-web-1 | mvp_intelligence | exited | missing-bind-source | source=<LOCAL_PATH:d12fa7f61011>/nginx.conf; destination=/etc/nginx/nginx.conf; expected=file; actual=missing |
| high | mvp_intelligence-web-1 | mvp_intelligence | exited | missing-bind-source | source=<LOCAL_PATH:db481afae7e8>/frontend; destination=/usr/share/nginx/html; expected=unspecified; actual=missing |
| high | mvp_intelligence-web-1 | mvp_intelligence | exited | missing-compose-file | <LOCAL_PATH:61328094fd45>/docker-compose.yml |
| high | redmine-app | redmine-docker | running | missing-compose-file | <LOCAL_PATH:cb2239146c41>/docker-compose.yml |
| high | redmine-db | redmine-docker | running | missing-compose-file | <LOCAL_PATH:cb2239146c41>/docker-compose.yml |
| high | redmine-proxy | redmine-docker | exited | bind-source-type-mismatch | source=<LOCAL_PATH:5d9ae133b2b0>/Caddyfile; destination=/etc/caddy/Caddyfile; expected=file; actual=directory |
| high | redmine-proxy | redmine-docker | exited | missing-compose-file | <LOCAL_PATH:cb2239146c41>/docker-compose.yml |
| high | reqsys-dev-kb-1 | reqsys-dev | running | missing-compose-file | <LOCAL_PATH:97dcc34a0091>/docker-compose.dev.yml |
| high | reqsys-dev-kb-1 | reqsys-dev | running | missing-compose-file | <LOCAL_PATH:846f1de38ec6>/docker-compose.yml |
| high | reqsys-dev-kb-1 | reqsys-dev | running | persistent-dev-restart | project=reqsys-dev; policy=unless-stopped |
| high | reqsys-live-api-1 | reqsys-live | running | persistent-dev-restart | project=reqsys-live; policy=unless-stopped |
| high | reqsys-live-frontend-1 | reqsys-live | running | persistent-dev-restart | project=reqsys-live; policy=unless-stopped |
| high | reqsys-prod-api-1 | reqsys-prod | running | missing-compose-file | <LOCAL_PATH:fb97e1182d23>/docker-compose.prod.yml |
| high | reqsys-prod-api-1 | reqsys-prod | running | missing-compose-file | <LOCAL_PATH:846f1de38ec6>/docker-compose.yml |
| high | reqsys-prod-frontend-1 | reqsys-prod | running | missing-compose-file | <LOCAL_PATH:fb97e1182d23>/docker-compose.prod.yml |
| high | reqsys-prod-frontend-1 | reqsys-prod | running | missing-compose-file | <LOCAL_PATH:846f1de38ec6>/docker-compose.yml |
| high | reqsys-prod-kb-1 | reqsys-prod | running | missing-compose-file | <LOCAL_PATH:846f1de38ec6>/docker-compose.yml |
| high | reqsys-prod-kb-1 | reqsys-prod | running | missing-compose-file | <LOCAL_PATH:fb97e1182d23>/docker-compose.prod.yml |
| high | reqsys-prod-nginx-1 | reqsys-prod | exited | bind-source-type-mismatch | source=<LOCAL_PATH:c74302271e6e>/default.prod.conf; destination=/etc/nginx/conf.d/default.conf; expected=file; actual=directory |
| high | reqsys-prod-nginx-1 | reqsys-prod | exited | missing-compose-file | <LOCAL_PATH:fb97e1182d23>/docker-compose.prod.yml |
| high | reqsys-prod-nginx-1 | reqsys-prod | exited | missing-compose-file | <LOCAL_PATH:846f1de38ec6>/docker-compose.yml |
| high | reqsys-selfhost-rehearsal-20261002-db-1 | reqsys-selfhost-rehearsal-20261002 | exited | unhealthy | state=exited; health=unhealthy |
| high | reqsys-selfhost-rehearsal2-20261002-api-1 | reqsys-selfhost-rehearsal2-20261002 | exited | unhealthy | state=exited; health=unhealthy |
| high | reqsys-selfhost-rehearsal2-20261002-db-1 | reqsys-selfhost-rehearsal2-20261002 | exited | unhealthy | state=exited; health=unhealthy |
| high | reqsys-test-api-1 | reqsys-test | exited | missing-compose-file | <LOCAL_PATH:846f1de38ec6>/docker-compose.yml |
| high | reqsys-test-api-1 | reqsys-test | exited | missing-compose-file | <LOCAL_PATH:136e7f15034f>/docker-compose.test.yml |
| high | reqsys-test-frontend-1 | reqsys-test | exited | historical-restart-storm | state=exited; restart_count=6991 |
| high | reqsys-test-frontend-1 | reqsys-test | exited | missing-compose-file | <LOCAL_PATH:136e7f15034f>/docker-compose.test.yml |
| high | reqsys-test-frontend-1 | reqsys-test | exited | missing-compose-file | <LOCAL_PATH:846f1de38ec6>/docker-compose.yml |
| high | reqsys-test-kb-1 | reqsys-test | exited | missing-compose-file | <LOCAL_PATH:846f1de38ec6>/docker-compose.yml |
| high | reqsys-test-kb-1 | reqsys-test | exited | missing-compose-file | <LOCAL_PATH:136e7f15034f>/docker-compose.test.yml |
| high | reqsys-test-nginx-1 | reqsys-test | exited | bind-source-type-mismatch | source=<LOCAL_PATH:b84dc3e3b888>/default.dev.conf; destination=/etc/nginx/conf.d/default.conf; expected=file; actual=directory |
| high | reqsys-test-nginx-1 | reqsys-test | exited | missing-compose-file | <LOCAL_PATH:136e7f15034f>/docker-compose.test.yml |
| high | reqsys-test-nginx-1 | reqsys-test | exited | missing-compose-file | <LOCAL_PATH:846f1de38ec6>/docker-compose.yml |
| high | reqsys-v2-enterprise-real-kb-1 | reqsys-v2-enterprise-real | running | missing-compose-file | <LOCAL_PATH:846f1de38ec6>/docker-compose.yml |
| high | reqsys-v2-enterprise-real-kb-1 | reqsys-v2-enterprise-real | running | missing-compose-file | <LOCAL_PATH:136e7f15034f>/docker-compose.test.yml |
