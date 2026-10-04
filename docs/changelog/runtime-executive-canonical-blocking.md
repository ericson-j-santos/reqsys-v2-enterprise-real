# Runtime Executive — Bloqueio Temporal Canônico

## Resumo

Promove o bloqueio temporal do `runtime-executive-regression-alert` para indicador executivo canônico nos contratos principais do Estado Único.

## Alterações

- Cria `scripts/enrich_runtime_executive_canonical_blocking.py`.
- Cria `scripts/validate_runtime_executive_canonical_blocking.py`.
- Atualiza `.github/workflows/ops-dashboard.yml` para enriquecer e validar os contratos antes da publicação do artifact.
- Atualiza `.github/workflows/runtime-validation-consolidator.yml` para publicar o mesmo sinal no artifact `runtime-validation-evidence`.

## Campos canônicos adicionados

No `Runtime Executive Index`:

- `summary.production_blocked`
- `summary.regression_alert_status`
- `summary.regression_alert_risk`
- `summary.regression_alert_violation_count`
- `cards.runtime_executive_regression_alert`
- `links.runtime_executive_regression_alert`

No `Executive Brief`:

- `estado_unico.production_blocked`
- `estado_unico.regression_alert_status`
- `estado_unico.runtime_executive_regression_alert`
- `indicadores_executivos.production_blocked`
- `indicadores_executivos.regression_alert_status`
- `indicadores_executivos.regression_alert_risk`
- `indicadores_executivos.regression_alert_violation_count`
- `semaforo_executivo.bloqueio_temporal`
- `links.runtime_executive_regression_alert`

## Guardrails

- Offline/read-only sobre artifacts locais.
- Sem secrets.
- Sem chamadas GitHub/API em runtime.
- Compatibilidade retroativa quando o artifact do regression alert ainda não existe.
- Bloqueio temporal canônico não executa deploy nem mutação remota.

## Próximo incremento seguro

Conectar o campo canônico `production_blocked` aos gates externos de deploy/liberação, mantendo o modo report-only por padrão e strict apenas nos workflows de promoção de ambiente.
