# Bootstrap dedicado — Cofre Runtime Service Token

## Objetivo
Criar/reutilizar no PC24x7 um ServiceToken ReqSys de privilégio mínimo para o Cofre Runtime Evidence Gate.

## Fluxo
PC24x7 → Cofre local `human_admin_jwt:dev` → API ReqSys `POST /v1/admin/service-tokens` → Azure Key Vault → validação `/v1/cofre/runtime/control-status`.

## Contrato
- label: `cofre-runtime-evidence-dev`
- scope: `cofre:runtime_evidence`
- secret: `reqsys-cofre-runtime-evidence-service-token`
- ambiente: DEV
- produção: não
- valor secreto em logs/artifacts: não

## Critérios
1. JWT humano nunca vem de GitHub Secret.
2. `VAULT_API_TOKEN` é lido somente no host e mascarado.
3. Token existente válido é reutilizado idempotentemente.
4. Token ausente/inválido só é recriado se `human_admin_jwt:dev` estiver válido.
5. Resultado publicado contém apenas status/metadados sanitizados.
6. O push desta especificação é o checkpoint canônico para disparar novamente o Pre-PR Readiness no HEAD exato.


## Critérios de aceite

- O modo `cofre-runtime` reutiliza o workflow canônico sem criar nova superfície.
- O token usa escopo mínimo `cofre:runtime_evidence` e secret dedicado no Key Vault.
- A validação ocorre em `/v1/cofre/runtime/control-status`.
- Teams permanece o modo padrão.
- Nenhum valor secreto é publicado em logs ou artifacts.
- O Cofre Runtime Evidence Gate autentica no Azure por OIDC e lê o token dedicado diretamente do Key Vault; não depende de cópia em GitHub Secrets.
