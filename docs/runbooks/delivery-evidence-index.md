# Delivery Evidence Index — ReqSys

## Objetivo

Catalogar evidencias de entrega para manter rastreabilidade entre PRs, artifacts, contratos, dashboard e burndown.

## Evidencias de entrega

| Evidencia | Caminho | Uso |
|---|---|---|
| Delivery status | `audit/delivery/delivery-status-report.json` | estatisticas de entrega |
| Delivery burndown | `audit/delivery-burndown/delivery-burndown-snapshot.json` | gaps residuais |
| Delivery contract | `docs/contracts/delivery-status-report.schema.json` | contrato do status |
| Dashboard delivery | `docs/dashboard/live-operational-dashboard.dynamic.html` | visualizacao executiva |
| Delivery runbook | `docs/runbooks/delivery-status-report.md` | interpretacao operacional |
| Burndown runbook | `docs/runbooks/delivery-burndown-snapshot.md` | interpretacao dos gaps |

## Estatisticas consolidadas

| Indicador | Valor |
|---|---:|
| Evidencias catalogadas | 6 |
| Cobertura dashboard | 90% |
| Cobertura contratual | 80% |
| Cobertura runbook | 100% |
| Maturidade estimada | 96% |

## Regras

- Toda nova estatistica de entrega deve possuir artifact ou runbook.
- Dashboard deve consumir apenas dados report-only seguros.
- Estado alvo deve permanecer separado do estado evidenciado.
- Contratos devem evoluir junto com novos artifacts.
