# PR Workflow Run Metrics

## Objetivo

Medir objetivamente a quantidade de workflows disparados por PR antes de expandir novos filtros por path.

## Artefato produzido

`docs/ops-dashboard/data/pr-workflow-run-metrics.json`

## Fonte esperada

`artifacts/github-actions/workflow-runs.json`

O script aceita snapshots em três formatos:

- lista direta de runs;
- objeto com `workflow_runs`;
- objeto com `runs`.

## Métricas principais

| Métrica | Uso |
|---|---|
| `average_workflows_per_pr` | Mede ruído médio por PR |
| `max_workflows_per_pr` | Detecta PRs que disparam workflows demais |
| `failed_runs` | Mostra retrabalho potencial |
| `queued_or_running_runs` | Evidencia fila e espera |

## Decisão Pareto

Só expandir roteamento por path quando houver evidência de quais workflows ainda dominam o tempo de fila.

## Execução local

```bash
python scripts/build_pr_workflow_run_metrics.py --json
```

## Validação

```bash
PYTHONPATH=. pytest -q tests/test_build_pr_workflow_run_metrics.py
```
