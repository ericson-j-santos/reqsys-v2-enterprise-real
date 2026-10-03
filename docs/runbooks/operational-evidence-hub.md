# Runbook — Operational Evidence Hub

## Objetivo

Consolidar em um único painel HTML estático e navegável todas as evidências operacionais report-only já existentes: delivery readiness, completion, finalization, maturity snapshot, observability correlation, artifact contract validation, dashboard regression validation e living architecture traceability.

## Entrada principal

| Item | Caminho |
|---|---|
| Hub consolidado | [`docs/dashboard/operational-evidence-hub.html`](../dashboard/operational-evidence-hub.html) |
| Validação estática | `npm run validate:dashboard-regression` |
| Relatório de regressão | [`docs/dashboard/dashboard-regression-report.md`](../dashboard/dashboard-regression-report.md) |

## Domínios consolidados

| Domínio | Artifact principal | Contrato | Runbook |
|---|---|---|---|
| Delivery readiness | `audit/delivery-readiness/delivery-readiness-report.json` | `docs/contracts/delivery-readiness-report.schema.json` | `docs/runbooks/delivery-evidence-index.md` |
| Delivery completion | `audit/delivery-completion/delivery-completion-snapshot.json` | `docs/contracts/delivery-completion-snapshot.schema.json` | `docs/runbooks/delivery-evidence-index.md` |
| Delivery finalization | `audit/delivery-finalization/delivery-finalization-report.json` | `docs/contracts/delivery-finalization-report.schema.json` | `docs/runbooks/ops-dashboard.md` |
| Maturity snapshot | `audit/delivery-maturity/delivery-maturity-snapshot.json` | `docs/contracts/delivery-maturity-snapshot.schema.json` | `docs/runbooks/delivery-maturity-snapshot.md` |
| Observability correlation | `artifacts/observability-correlation-report/observability-correlation-report.json` | `docs/contracts/observability-correlation-report.schema.json` | `docs/runbooks/observability-correlation-report.md` |
| Artifact contract validation | `audit/artifact-contract-validation/artifact-contract-validation-report.json` | `docs/contracts/artifact-contract-validation-report.schema.json` | `docs/runbooks/operational-artifact-schema-validation.md` |
| Dashboard regression | `docs/dashboard/dashboard-regression-report.json` | — | `docs/runbooks/dashboard-regression-validation.md` |
| Living architecture traceability | `audit/living-architecture/living-architecture-traceability-report.json` (fallback: `docs/traceability/living-architecture-map.json`) | `docs/contracts/living-architecture-map.schema.json` | `docs/runbooks/living-architecture-traceability.md` |

## Como abrir localmente

```bash
# A partir da raiz do repositório, sirva docs/dashboard/ com um servidor estático simples:
cd docs/dashboard
python3 -m http.server 8765
# Acesse http://127.0.0.1:8765/operational-evidence-hub.html
```

Ou abra o arquivo diretamente no navegador; o `fetch` local funciona quando servido por HTTP (não via `file://` em alguns navegadores).

## Fallback governado

Quando um artifact não estiver presente no repositório (típico antes da execução do workflow produtor), o hub:

1. Tenta carregar o caminho primário declarado.
2. Para rastreabilidade, tenta `docs/traceability/living-architecture-map.json` como alternativa.
3. Usa objeto `fallback[domain.key]` com valores neutros e semáforo de atenção.
4. Marca a fonte como `fallback` na tabela de fontes.

## Indicadores exibidos

- **Cards executivos** com drill-down por seção.
- **Semáforo** (`verde` / `amarelo` / `vermelho`) por domínio e linha de tabela.
- **Confidence level** e **operational risk** quando presentes no artifact.
- **Links** para dashboards existentes, contratos e runbooks — sem remover painéis anteriores.

## Validação

```bash
npm run validate:dashboard-regression
```

O script valida:

- presença do hub em `docs/dashboard/operational-evidence-hub.html`;
- cards executivos obrigatórios;
- referências às fontes JSON esperadas;
- seções de drill-down navegáveis;
- fallback seguro (`loadJson`, `try/catch`, `fallback[domain.key]`);
- indicadores de governança (`confidence_level`, `operational_risk`, semáforo);
- ausência de secrets e chamadas externas não governadas.

## Regras operacionais

- Modo **report-only**: não substitui gates obrigatórios de CI ou merge.
- Não altera runtime produtivo, deploy ou autenticação.
- Estado alvo não deve ser confundido com estado evidenciado.
- Novos artifacts devem ser adicionados ao hub e ao índice de rastreabilidade na mesma rodada ou na seguinte.

## Dashboards relacionados (preservados)

- [`live-operational-dashboard.dynamic.html`](../dashboard/live-operational-dashboard.dynamic.html)
- [`delivery-finalization-panel.html`](../dashboard/delivery-finalization-panel.html)
- [`ops-dashboard/index.html`](../ops-dashboard/index.html)
