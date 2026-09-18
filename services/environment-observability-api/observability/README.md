# Dashboards e alertas

Este diretório contém os ativos operacionais da Environment Observability API.

## Arquivos

- `grafana-dashboard.json`: dashboard importável no Grafana;
- `prometheus-alerts.yaml`: regras de alerta para Prometheus/Alertmanager.

## Fontes esperadas

A API deve ser coletada em `/metrics`. O Collector deve disponibilizar suas métricas internas em `:8888` com o job `environment-observability-collector`.

## Alertas cobertos

- taxa de erro HTTP superior a 5%;
- latência p95 superior a um segundo;
- ausência de tráfego;
- falha de exportação de spans;
- spans recusados pelo receiver;
- fila do Collector acima de 80%;
- Collector indisponível.

## Segregação por ambiente

Use instâncias, pastas ou datasources separados para `development`, `staging` e `production`. Não reutilize credenciais entre ambientes. A variável de ambiente do dashboard deve filtrar apenas labels controladas e de baixa cardinalidade.

## Provisionamento

Grafana: importe `grafana-dashboard.json` ou use o provisionamento nativo de dashboards.

Prometheus: inclua `prometheus-alerts.yaml` em `rule_files` e valide antes da publicação:

```bash
promtool check rules observability/prometheus-alerts.yaml
```

## Evidência operacional mínima

Após o deploy, registrar por ambiente:

1. health do Collector;
2. scrape da API e do Collector;
3. painel com tráfego real;
4. teste controlado de alerta;
5. rota de notificação validada;
6. evidência de recuperação após normalização.
