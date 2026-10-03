# Ops Dashboard — Regression Alert no Card Post-Deploy

## Resumo

Expõe o `runtime_executive_regression_alert` visualmente dentro do card Runtime Executive Post-Deploy do Ops Dashboard.

## Alterações

- Atualiza `scripts/inject_ops_dashboard_runtime_executive_post_deploy_card.py`.
- Atualiza `scripts/validate_ops_dashboard_runtime_executive_post_deploy_card.py`.
- O card passa a consumir o artifact `runtime-executive-regression-alert.json`.

## Sinais exibidos

- Status do regression alert.
- Risco de regressão.
- Produção bloqueada.
- Quantidade de violações.
- Lista de violações com severidade, observado, threshold e detalhe.
- Thresholds governados no drill-down.

## Guardrails

- Dashboard estático.
- Sem GitHub API em runtime.
- Sem secrets.
- Fallback seguro quando o artifact do alert ainda não existe.
- Validação offline/read-only.

## Próximo incremento seguro

Conectar o regression alert ao semáforo executivo principal do Ops Dashboard, permitindo que bloqueio temporal seja refletido no topo do painel executivo.
