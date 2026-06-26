# Ops Dashboard

## Objetivo

Disponibilizar um painel operacional estatico para leitura rapida do estado do ReqSys, com foco em CI, evidencias, PRs de risco e saude da branch `main`.

## Entregas

- `docs/ops-dashboard/index.html`
- `docs/ops-dashboard/data/health.json`
- `scripts/generate_ops_dashboard_data.py`
- `.github/workflows/ops-dashboard.yml`

## Funcionamento

O workflow `Ops Dashboard` gera o artifact `ops-dashboard-static` contendo o HTML e o JSON de dados.

Nesta versao, o painel usa dados locais/fallback, consome o relatorio do `Repository Health Watchdog` quando presente e integra `runtime-health-report.json` e `runtime-operational-evidence-graph.json` quando publicados localmente. O dashboard inclui drill-down por dominio e Incident Timeline filtravel por severidade, dominio e status.

## Gatilhos

- `workflow_dispatch` manual;
- `workflow_run` apos conclusao do `Repository Health Watchdog`.

## Fora do escopo

Este incremento nao:

- publica automaticamente em producao;
- altera GitHub Pages;
- altera secrets;
- executa deploy;
- fecha PR;
- faz merge automatico.

## Incremento REQSYS#323

O incremento `REQSYS#323 — Runtime Dashboard Drill-down + Incident Timeline` adiciona:

- drill-down por dominio com health, evidencias disponiveis/faltantes, risco, drift de ambiente e governanca;
- Incident Timeline local consolidando eventos por workflow, PR e dominio;
- filtros client-side por severidade, dominio e status;
- integracao opcional dos artifacts `runtime-health-report.json` e `runtime-operational-evidence-graph.json`;
- contrato JSON `schema_version=1.1.0` para consumo estatico sem rede externa.

## Proximo incremento recomendado

Baixar artifacts historicos aprovados para trendline temporal, mantendo execucao review-only e sem GitHub Pages/deploy automatico.

## Criterios de aceite

- Workflow `Ops Dashboard` concluido com sucesso.
- Artifact `ops-dashboard-static` publicado.
- `index.html` abre localmente sem CDN.
- `data/health.json` existe.
- Sem permissao de escrita ou deploy automatico.
