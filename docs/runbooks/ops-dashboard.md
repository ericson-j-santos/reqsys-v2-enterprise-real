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

Nesta versao, o painel usa dados locais/fallback e esta preparado para consumir o relatorio do `Repository Health Watchdog` quando o artifact for integrado ao pipeline.

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

## Proximo incremento recomendado

Integrar download do artifact `repository-health-watchdog-report` para alimentar o dashboard com o ultimo relatorio real, e depois habilitar GitHub Pages com aprovacao humana.

## Criterios de aceite

- Workflow `Ops Dashboard` concluido com sucesso.
- Artifact `ops-dashboard-static` publicado.
- `index.html` abre localmente sem CDN.
- `data/health.json` existe.
- Sem permissao de escrita ou deploy automatico.
