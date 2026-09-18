# Runtime Executive Regression Alert

## Resumo

Adiciona gate de regressão temporal para o Runtime Executive Post-Deploy, com bloqueio governado de produção em modo strict quando houver violação crítica.

## Alterações

- Cria `scripts/evaluate_runtime_executive_temporal_regression.py`.
- Cria `scripts/validate_runtime_executive_regression_alert.py`.
- Atualiza `.github/workflows/runtime-executive-post-deploy-smoke.yml` para avaliar regressão temporal após o histórico.
- Atualiza `.github/workflows/runtime-validation-consolidator.yml` para consolidar o alerta no Estado Único.
- Atualiza `.github/workflows/ops-dashboard.yml` para publicar o artifact `runtime-executive-regression-alert`.

## Regras de bloqueio

O gate bloqueia produção quando:

- `availability_percent` fica abaixo de `95%`;
- `avg_latency_ms` fica acima de `2500 ms`;
- taxa de falha recente fica acima de `20%` na janela governada;
- opcionalmente, quando o score executivo cai por execuções consecutivas com `--block-on-score-drop`.

## Contrato publicado

- `artifacts/runtime-executive-regression-alert/runtime-executive-regression-alert.json`

## Executive Brief

O Executive Brief passa a receber:

- `estado_unico.runtime_executive_regression_alert`
- `indicadores_executivos.runtime_executive_regression_risk`
- `indicadores_executivos.runtime_executive_regression_blocked`
- `links.runtime_executive_regression_alert`

## Guardrails

- Offline/read-only.
- Sem secrets.
- Thresholds parametrizados.
- Strict mode bloqueia produção somente quando houver regressão crítica.
- Histórico ausente gera warning, não bloqueio imediato.

## Próximo incremento seguro

Expor o `runtime_executive_regression_alert` no Ops Dashboard como indicador visual próprio dentro do card post-deploy, destacando violations e estado de bloqueio de produção.
