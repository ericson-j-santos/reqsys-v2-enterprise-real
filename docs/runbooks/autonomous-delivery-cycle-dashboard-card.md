# Autonomous Delivery Cycle — Dashboard Card

## Objetivo

Expor os contratos do `Autonomous Delivery Cycle` no dashboard operacional estático, sem chamadas runtime ao GitHub.

## Entradas

- `docs/ops-dashboard/data/autonomous-delivery-cycle-latest.json`
- `docs/ops-dashboard/data/autonomous-delivery-cycle-next-increments.json`

## Saída

- `docs/ops-dashboard/data/autonomous-delivery-cycle-dashboard-card.json`

## Builder

```bash
python scripts/build_autonomous_delivery_cycle_dashboard_card.py
```

## Guardrails

- geração offline;
- fallback seguro quando artifacts estiverem ausentes;
- fila de próximos incrementos permanece report-only;
- atenção pós-merge classifica risco alto;
- não executa merge nem novos incrementos.

## Próximo incremento natural

Renderizar `autonomous-delivery-cycle-dashboard-card.json` na UI operacional do dashboard público.
