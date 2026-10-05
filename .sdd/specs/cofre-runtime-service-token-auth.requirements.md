# Cofre Runtime Evidence — autenticação S2S

## Objetivo
Eliminar JWT administrativo humano expirável do caminho operacional do Cofre Gate.

## Requisitos
1. Runtime-control aceita `X-Service-Token`.
2. Service token tem escopo mínimo `cofre:runtime_evidence`.
3. Cofre Gate usa somente `COFRE_RUNTIME_SERVICE_TOKEN`.
4. Bootstrap permite label/escopo/secret/rota de validação dedicados.
5. JWT humano, quando necessário, existe apenas na emissão inicial do service token.
6. Ausência ou token inválido falha fechado.

## Provisionamento alvo
- label: `cofre-runtime-evidence-dev`
- scope: `cofre:runtime_evidence`
- Key Vault secret: `reqsys-cofre-runtime-evidence-service-token`
- validation path: `/v1/cofre/runtime/control-status`

## Critérios de aceite
- CI e testes verdes no HEAD exato.
- Workflow não contém `COFRE_ADMIN_JWT`.
- Gate autenticado por service token comprova runtime same-SHA.
- Nenhum valor secreto aparece em logs/evidências.
