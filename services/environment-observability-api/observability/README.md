# Dashboards e alertas

Este diretório contém os ativos operacionais da Environment Observability API.

## Arquivos

- `grafana-dashboard.json`: dashboard importável no Grafana;
- `prometheus-alerts.yaml`: regras de alerta para Prometheus/Alertmanager;
- `dev/prometheus.yml` e `dev/alertmanager.yml`: stack local DEV;
- `stg/prometheus.yml` e `stg/alertmanager.yml`: contrato STG sem segredo versionado;
- `prod/prometheus.yml` e `prod/alertmanager.yml`: contrato PROD sem segredo versionado.

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

## Contrato STG/PROD

Os arquivos `compose.observability.stg.yml` e `compose.observability.prod.yml` materializam a topologia por ambiente sem publicar portas em interfaces públicas e sem versionar segredos.

Garantias mínimas:

1. todos os serviços expõem portas apenas em `127.0.0.1`;
2. a rede `observability` permanece interna;
3. `APP_ENV` diferencia `staging` e `production`;
4. volumes de Collector, Prometheus e Grafana são separados por ambiente;
5. senhas, tokens e webhooks devem entrar apenas por variáveis externas ou cofre;
6. a rota de notificação STG/PROD fica explicitamente pendente até haver segredo aprovado e evidência real;
7. nenhum arquivo deste diretório comprova deploy físico ou promoção de produção por si só.

## Provisionamento

Grafana: importe `grafana-dashboard.json` ou use o provisionamento nativo de dashboards.

Prometheus: inclua `prometheus-alerts.yaml` em `rule_files` e valide antes da publicação:

```bash
promtool check rules observability/prometheus-alerts.yaml
```

## Evidência operacional mínima

Após o deploy autorizado, registrar por ambiente:

1. health do Collector;
2. scrape da API e do Collector;
3. painel com tráfego real;
4. teste controlado de alerta;
5. rota de notificação validada;
6. evidência de recuperação após normalização;
7. artifact com `environment`, `head_sha`, `run_id`, `correlation_id`, início, fim, alerta ativo e alerta resolvido.
