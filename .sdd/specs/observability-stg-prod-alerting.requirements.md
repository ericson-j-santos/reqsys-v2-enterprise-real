# Observabilidade STG/PROD — Requisitos

## Objetivo

Preparar o contrato de observabilidade de STG e PROD sem promover ambientes, sem versionar segredos e sem produzir falso positivo de notificação.

## Requisitos

1. Serviços de observabilidade devem publicar portas apenas em `127.0.0.1`.
2. A rede interna de observabilidade deve permanecer isolada.
3. Segredos de Grafana e autorização OTEL devem ser referenciados por variáveis de ambiente, nunca por valores literais versionados.
4. Alertmanager de STG e PROD deve permanecer em estado de notificação pendente até configuração autorizada do canal real.
5. Prometheus deve etiquetar explicitamente o ambiente e manter retenção diferenciada por ambiente.

## Critérios de aceite

1. O teste `services/environment-observability-api/tests/test_stg_prod_observability_contract.py` passa sem aceitar segredo literal.
2. O placeholder obrigatório `${STG_GRAFANA_ADMIN_PASSWORD:?required}` é aceito como referência segura, não como senha versionada.
3. O placeholder obrigatório `${PROD_GRAFANA_ADMIN_PASSWORD:?required}` é aceito como referência segura, não como senha versionada.
4. Não existem `webhook_url`, `api_key`, URL de Teams/Office ou bearer token literal nos contratos STG/PROD.
5. Nenhum deploy ou promoção de STG/PROD é executado por este incremento.
