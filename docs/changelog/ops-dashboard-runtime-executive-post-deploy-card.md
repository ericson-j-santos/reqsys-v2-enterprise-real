# Ops Dashboard — Runtime Executive Post-Deploy Card

## Resumo

Adiciona card dedicado do Runtime Executive Post-Deploy ao Ops Dashboard publicado como artifact estático.

## Alterações

- Cria `scripts/inject_ops_dashboard_runtime_executive_post_deploy_card.py`.
- Cria `scripts/validate_ops_dashboard_runtime_executive_post_deploy_card.py`.
- Atualiza `.github/workflows/ops-dashboard.yml` para injetar o card antes da publicação do artifact.
- Valida o card durante o quality gate do Ops Dashboard.

## Dados consumidos

O card consome exclusivamente:

- `./data/executive-brief.json`

Campos esperados:

- `estado_unico.runtime_executive_post_deploy`
- `semaforo_executivo.runtime_executive_publico`
- `indicadores_executivos.runtime_executive_post_deploy_percent`
- `links.runtime_executive_public_page`
- `links.runtime_executive_public_contract`

## Guardrails

- Dashboard permanece estático.
- Sem chamada GitHub/API em runtime.
- Sem token/segredo no frontend.
- Fallback local seguro quando o Executive Brief não contém a evidência pós-deploy.

## Próximo incremento seguro

Adicionar histórico temporal do Runtime Executive Post-Deploy para acompanhar tendência de disponibilidade, latência e falhas nas últimas execuções.
