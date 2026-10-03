# Runtime Executive Post-Deploy no Estado Único

## Resumo

Integra a evidência `runtime-executive-post-deploy-smoke` ao Runtime Validation Consolidator e ao Executive Brief.

## Alterações

- Cria `scripts/enrich_runtime_validation_with_post_deploy_smoke.py`.
- Atualiza `.github/workflows/runtime-validation-consolidator.yml`.
- Adiciona trigger `workflow_run` para `Runtime Executive Post-Deploy Smoke`.
- Baixa o artifact `runtime-executive-post-deploy-smoke` durante a consolidação.
- Enriquece:
  - `artifacts/runtime-validation-consolidator/runtime-validation-snapshot.json`;
  - `docs/ops-dashboard/data/executive-brief.json`.

## Estado Único

O snapshot passa a receber o domínio:

- `runtime_executive_post_deploy`

O Executive Brief passa a refletir:

- semáforo `runtime_executive_publico`;
- indicador `runtime_executive_post_deploy_percent`;
- links públicos da página e do contrato, quando disponíveis;
- estado de produção recalculado com base no endpoint real.

## Guardrails

- Integração offline/read-only.
- Não executa deploy.
- Não faz chamadas externas.
- Não captura secrets.
- Mantém o consolidator original estável, usando adapter pós-processamento.

## Próximo incremento seguro

Expor o domínio `runtime_executive_post_deploy` no Ops Dashboard como card próprio, com drill-down para page URL, contract URL, status HTTP, latência e failures.
