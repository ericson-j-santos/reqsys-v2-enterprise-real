# Completion Projection Report — ReqSys

## Objetivo

Consolidar a projecao estatistica de conclusao do ReqSys em um artifact governado
(JSON + Markdown), mantendo rastreabilidade entre estado atual, velocidade,
percentuais de conclusao, gaps, projecao de tempo, risco, tendencia e
probabilidades. O artifact alimenta o command center e e estritamente report-only.

## Fonte e geracao

- Gerador: `scripts/completion_projection_report.py`.
- Contrato: `docs/contracts/completion-projection-report.schema.json`.
- Workflow: `.github/workflows/completion-projection-report.yml`.
- Saida: `audit/projection/completion-projection-report.json` e `.md`.

Execucao local:

```bash
python scripts/completion_projection_report.py --output-dir audit/projection
```

## Indicadores derivados

| Indicador | Origem |
|---|---|
| `overall_completion_percent` | media de `completion[].percent` |
| `average_maturity_percent` | media de `current_state[].status_percent` |
| `average_gap_pp` | media de `gaps[].gap_percent` |
| `remaining_to_gold_pp` | `100 - padrao_ouro_total_consolidado` |
| `status` | derivado de conclusao geral + probabilidade de MVP |

## Referencia temporal

- Snapshot da projecao: `2026-06-27T21:00:00-03:00` (BRT).

## Regras de atualizacao

- Atualizar os tabelas-fonte no gerador a cada nova projecao executiva.
- Manter conclusao geral, maturidade e gap derivados das tabelas (sem hardcode duplicado).
- Separar estado projetado de estado evidenciado; nao declarar 100% sem evidencia.
- Report-only nao substitui CI obrigatorio nem gates de producao.

## Consumo

- Dashboard dinamico: `docs/dashboard/live-operational-dashboard.dynamic.html`.
- Indice de evidencias: `docs/dashboard/command-center-evidence-index.md`.
- Mapa navegavel: `docs/dashboard/command-center-navigation-map.md`.
