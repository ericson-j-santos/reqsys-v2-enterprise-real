# Environment Promotion Readiness

## Resumo

Adiciona evidência executiva consolidada para promoção DEV → STG → PROD baseada em:

- Executive Readiness Gate.
- Runtime Executive Index.
- Evidências do Fly Environment Homologation Gate para `dev`, `stg` e `prod`.

## Resposta objetiva sobre ambientes

Antes deste incremento, o ReqSys já tinha gate manual por ambiente em `.github/workflows/fly-environment-homologation-gate.yml`, mas não havia um contrato executivo único exigindo evidência dos três ambientes criados antes da promoção para produção.

Este incremento cria esse contrato.

## Saída

- `artifacts/environment-promotion-readiness/environment-promotion-readiness.json`

## Decisões possíveis

- `READY_FOR_PROD_PROMOTION`
- `BLOCKED_FOR_PROD_PROMOTION`

## Ambientes obrigatórios

- `dev`
- `stg`
- `prod`

## Guardrails

- Report-only por padrão.
- Sem deploy.
- Sem secrets.
- Sem chamada GitHub/API em runtime público.
- Produção bloqueada quando faltar evidência de qualquer ambiente.
- Produção bloqueada quando Executive Readiness não estiver pronto.
- Validação de divergência de SHA quando `expected_sha` for informado.

## Workflow

- `.github/workflows/environment-promotion-readiness.yml`

O workflow executa testes unitários, gera o contrato, valida o schema e publica artifact.

## Próximo incremento seguro

Conectar `environment-promotion-readiness.json` ao Ops Dashboard como indicador executivo de topo para promoção entre ambientes.
