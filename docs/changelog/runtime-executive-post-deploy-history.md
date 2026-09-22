# Runtime Executive Post-Deploy History

## Resumo

Adiciona histórico temporal append-only e limitado do Runtime Executive Post-Deploy, consolidando disponibilidade, latência, falhas, tendência e estabilidade operacional no Estado Único.

## Alterações

- Cria `scripts/build_runtime_executive_post_deploy_history.py`.
- Cria `scripts/validate_runtime_executive_post_deploy_history.py`.
- Atualiza `.github/workflows/runtime-executive-post-deploy-smoke.yml` para gerar e publicar o histórico.
- Atualiza `.github/workflows/runtime-validation-consolidator.yml` para baixar, consolidar e publicar o histórico no `runtime-validation-evidence`.
- Atualiza `.github/workflows/ops-dashboard.yml` para publicar `data/runtime-executive-post-deploy-history.json` no artifact `ops-dashboard-static`.
- Evolui o card do Runtime Executive Post-Deploy no Ops Dashboard para exibir série temporal e indicadores agregados.

## Contrato publicado

- `docs/ops-dashboard/data/runtime-executive-post-deploy-history.json`
- `artifacts/runtime-executive-post-deploy-history/runtime-executive-post-deploy-history.json`

## Métricas consolidadas

- `samples`
- `availability_percent`
- `avg_latency_ms`
- `max_latency_ms`
- `failure_count`
- `score_trend`
- `latency_trend`
- `failure_trend`
- `mtbf_hours`
- `stability`

## Executive Brief

O Executive Brief passa a receber:

- `estado_unico.runtime_executive_post_deploy_history`
- `indicadores_executivos.runtime_executive_post_deploy_availability_percent`
- `indicadores_executivos.runtime_executive_post_deploy_avg_latency_ms`
- `indicadores_executivos.runtime_executive_post_deploy_stability`
- `links.runtime_executive_post_deploy_history`

## Guardrails

- Histórico append-only e limitado a 200 amostras por padrão.
- Sem banco de dados.
- Sem secrets.
- Sem chamadas externas no consolidator/history builder.
- Baseado em artifacts JSON.
- Mantém compatibilidade com contratos existentes.

## Próximo incremento seguro

Adicionar alerta de regressão temporal para bloquear produção quando a tendência de disponibilidade cair, a latência subir acima do limite ou a taxa de falha recente ultrapassar o limiar governado.
