# GitHub Actions History Lake

## Objetivo

Usar o histórico público/operacional do GitHub Actions como fonte inicial para baseline temporal longa do ReqSys, permitindo evolução da precisão estatística de entrega.

## Estado implementado

- Coletor Python governado em `scripts/github_actions_history_lake.py`.
- Saídas JSONL, JSON, Markdown e HTML.
- Deduplicação por `run_id` + `run_attempt`.
- Métricas críticas: success rate, blocking failure rate, duração média, risco estimado e precisão estimada.
- Sem deploy.
- Sem escrita externa.
- Sem alteração de secrets.
- Sem chamada a IA externa.

## Arquitetura

```text
GitHub Actions API
        ↓
scripts/github_actions_history_lake.py
        ↓
data/operational/github-actions-history/runs.jsonl
        ↓
artifacts/github-actions-history-lake/
        ↓
Predictive Governance / Stability Layer
```

## Execução manual local ou CI

```bash
GITHUB_TOKEN=<token> python scripts/github_actions_history_lake.py \
  --repo ericson-j-santos/reqsys-v2-enterprise-real \
  --branch main \
  --pages 5 \
  --per-page 100 \
  --data-path data/operational/github-actions-history/runs.jsonl \
  --output-dir artifacts/github-actions-history-lake
```

## Indicadores gerados

- `precision_estimate_percent`
- `risk_estimate_percent`
- `success_rate_percent`
- `blocking_failure_rate_percent`
- `average_duration_seconds`
- `readiness_state`

## Limite operacional

O GitHub continua sendo fonte operacional. O histórico longo deve ser persistido pelo ReqSys em JSONL/versionamento próprio para evitar dependência de retenção limitada de logs e artifacts.

## Próximo incremento recomendado

Adicionar workflow agendado seguro para publicar artifacts do coletor. A criação de workflow automático deve permanecer governada e sem auto-commit até validação humana.
