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

Nesta versao, o painel usa dados locais/fallback, consome o relatorio do `Repository Health Watchdog` quando presente e integra `runtime-health-report.json`, `runtime-operational-evidence-graph.json` e `delivery-finalization-report.json` quando publicados localmente. O dashboard inclui drill-down por dominio, Incident Timeline filtravel por severidade, dominio e status, e uma leitura report-only de finalizacao da entrega.

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
- contrato JSON `schema_version=1.2.0` para consumo estatico sem rede externa.

## Proximo incremento recomendado

Baixar artifacts historicos aprovados para trendline temporal, mantendo execucao review-only e sem GitHub Pages/deploy automatico.

## Criterios de aceite

- Workflow `Ops Dashboard` concluido com sucesso.
- Artifact `ops-dashboard-static` publicado.
- `index.html` abre localmente sem CDN.
- `data/health.json` existe.
- Sem permissao de escrita ou deploy automatico.

## Incremento — Delivery Finalization Dashboard Integration

O incremento adiciona consumo opcional e seguro do artifact `artifacts/delivery-finalization/delivery-finalization-report.json` pelo gerador `scripts/generate_ops_dashboard_data.py`.

### Campos expostos no dashboard

- Card de score final (`final_score`, `score_final`, `score` ou `completion_score`).
- Card de gap residual (`residual_gap`, `gap_residual` ou `gap`).
- Card de status (`status`, `overall_status` ou `final_status`).
- Card de indicadores aprovados versus total.
- Tabela drill-down de `indicators`/`indicadores`, com status, score, gap e evidencia local.

### Fallback seguro

Quando o artifact nao existir, o JSON gerado preserva `delivery_finalization.available=false`, `status=unknown`, contadores zerados e mensagem de guardrail. O HTML renderiza o fallback sem tentar chamadas externas, sem bloquear cards existentes e sem modificar runtime produtivo.

### Evidencias locais esperadas

```bash
python -m unittest tests/test_ops_dashboard_data.py
python scripts/generate_ops_dashboard_data.py --repo example/repo --output /tmp/reqsys-ops-health.json
python -m py_compile scripts/generate_ops_dashboard_data.py
```

### Fora de escopo do incremento

- Nao cria deploy, GitHub Pages ou alteracao de producao.
- Nao adiciona secrets.
- Nao adiciona chamadas externas.
- Nao substitui os gates obrigatorios de CI.
