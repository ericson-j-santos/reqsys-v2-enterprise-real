# ADR-038 — Trilha C: UX Operacional

## Status

Aceito em 2026-06-27.

## Contexto

Monitoramento operacional e analytics já existiam na SPA com semáforo, cards clicáveis e drill-down, mas sem pacote de governança padrão ouro (ADR, runbook, validador, schema).

## Decisão

Formalizar a **Trilha C — UX Operacional** com cinco capacidades:

| Capacidade | Artefato |
|---|---|
| Semáforo operacional | `SemaforoChip.vue`, `filtrosMonitoramento.js` |
| Drill-down | `OperationalMetricCard.vue`, `runtimeDashboard.js` |
| Monitoramento | `MonitoramentoOperacionalView.vue`, rota `/monitoramento-operacional` |
| Analytics hub | `AnalyticsHubView.vue`, rota `/analytics` |
| Responsividade | `rotasResponsivas.js` (19 rotas canônicas) |

Validação report-only via `scripts/trilha_c_ux_operacional.py`.

## Regras de governança

| Tema | Decisão |
|---|---|
| Modo | `report_only` |
| Fluxo analítico | Indicador → card → drill-down → ação operacional |
| Responsividade | Rotas C incluídas no gate E2E responsivo |
| Schema-driven | Cards consomem runtime dashboard schema-driven quando disponível |

## Consequências

### Benefícios

- UX operacional auditável e versionada.
- Alinhamento explícito com padrão ouro transversal de drill-down.

### Limitações

- Validador verifica estrutura estática; regressão visual continua no Playwright.
- Integração profunda com hub Trilha E fica para incremento futuro.

## Referências

- `docs/adr/ADR-0006-analytics-drilldown-schema-driven-ui.md`
- `docs/runbooks/trilha-c-ux-operacional.md`
- `frontend/tests/e2e/responsividade.spec.js`
