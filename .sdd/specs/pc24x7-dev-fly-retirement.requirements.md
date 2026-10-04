# PC24x7 DEV — aposentadoria do Fly automático

## Objetivo

Retirar Fly da rota automática de DEV sem remover os controles legados de HML/PROD que ainda exigem acionamento manual explícito.

## Requisitos

1. `fly-automatic-environment-promotion.yml` deve ser `workflow_dispatch` only.
2. O workflow legado não pode conter `schedule` nem `workflow_run`.
3. DEV deve ser validado exclusivamente em PC24x7; não pode existir `Capture DEV via Fly`, `Promote DEV via Fly` ou provider `fly|pc24x7`.
4. HML/PROD Fly podem permanecer somente no fluxo manual e sujeitos aos gates existentes.
5. `auto-public-runtime-evidence.yml` deve usar `Main Post-Merge Validation` fail-closed como upstream.
6. A URL DEV deve vir do locator assinado PC24x7 e `fly.io/fly.dev` deve ser rejeitado.
7. O gate `validate_dev_runtime_cutover.py` deve detectar qualquer regressão dessas invariantes.
8. Nenhuma mudança deve tocar produção, segredo ou permissão administrativa.

## Critérios de aceite

- testes negativos provam ausência de gatilho Fly automático;
- testes provam ausência de fallback Fly em DEV;
- auto-public usa PC24x7 e locator assinado;
- SDD, sintaxe YAML/Python, regressão de workflows e Pre-PR Readiness passam no HEAD exato;
- `behind_by=0` antes da PR.
