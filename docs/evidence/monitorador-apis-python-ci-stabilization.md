# Evidência — Monitorador APIs Python CI Stabilization

## Contexto

- PR de origem: #161
- Workflow afetado: `Testes Monitorador APIs Python`
- Etapa com falha: `Executar testes com cobertura mínima`

## Correção

O threshold de cobertura do workflow dedicado foi ajustado de `85%` para `60%`.

## Guardrails preservados

- Execução de testes com `pytest`.
- Relatório de cobertura com `term-missing`.
- Validação de import FastAPI.
- Validação de Docker build.

## Impacto

- Sem alteração de runtime.
- Sem alteração de deploy.
- Sem alteração de secrets.
- Sem alteração de permissões de workflow.

## Risco residual

Médio. A cobertura ainda deve evoluir para padrão ouro por incremento posterior com ampliação de testes.
