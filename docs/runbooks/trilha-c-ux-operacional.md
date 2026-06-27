# Trilha C — UX Operacional

**Data:** 2026-06-27  
**ADR:** [`docs/adr/ADR-038-trilha-c-ux-operacional.md`](../adr/ADR-038-trilha-c-ux-operacional.md)

## Objetivo

Operar semáforo, drill-down, analytics navegável e responsividade das telas operacionais — sem alterar backend crítico.

## Artefatos canônicos

| Item | Caminho |
|---|---|
| Architecture-as-Code | [`docs/architecture/trilha-c/architecture-as-code.json`](../architecture/trilha-c/architecture-as-code.json) |
| Monitoramento | [`frontend/src/views/MonitoramentoOperacionalView.vue`](../../frontend/src/views/MonitoramentoOperacionalView.vue) |
| Analytics Hub | [`frontend/src/views/AnalyticsHubView.vue`](../../frontend/src/views/AnalyticsHubView.vue) |
| Semáforo | [`frontend/src/components/SemaforoChip.vue`](../../frontend/src/components/SemaforoChip.vue) |
| Cards operacionais | [`frontend/src/components/OperationalMetricCard.vue`](../../frontend/src/components/OperationalMetricCard.vue) |
| Rotas responsivas | [`frontend/src/constants/rotasResponsivas.js`](../../frontend/src/constants/rotasResponsivas.js) |
| Schema | [`docs/contracts/trilha-c-ux-operacional.schema.json`](../contracts/trilha-c-ux-operacional.schema.json) |
| Gerador | [`scripts/trilha_c_ux_operacional.py`](../../scripts/trilha_c_ux_operacional.py) |
| Workflow | [`.github/workflows/trilha-c-ux-operacional.yml`](../../.github/workflows/trilha-c-ux-operacional.yml) |

## Rotas canônicas

| Rota | View | testId |
|---|---|---|
| `/monitoramento-operacional` | MonitoramentoOperacionalView | `route-monitoramento-operacional` |
| `/analytics` | AnalyticsHubView | `route-analytics` |

## Validação local

```bash
python scripts/trilha_c_ux_operacional.py
cat audit/trilha-c/trilha-c-ux-operacional-report.json

cd frontend && npm run build
npx playwright test tests/e2e/responsividade.spec.js --grep "monitoramento|analytics"
```

## Fluxo analítico

```text
Indicador (card) → semáforo → drill-down → rota filtrada → ação operacional
```

## Critério de pronto

1. Views C com eyebrow e componentes schema-driven.
2. Rotas registradas no router e em `rotasResponsivas.js`.
3. Build frontend verde.
4. Workflow publica artifact `trilha-c-ux-operacional-${{ github.run_id }}`.

## Relação com outras trilhas

- **Trilha B** fornece telemetria consumida pelos cards.
- **Trilha D** valida E2E responsivo no gate CI.
