# Teams Bot DEV Identity Bootstrap Automation

## Objetivo

Automatizar, com custo adicional zero e de forma governada, a execução idempotente do bootstrap da identidade dedicada `ReqSys Teams Bot DEV`, reutilizando a sessão Microsoft Entra delegada existente no host Noteri e sem conceder `Application.ReadWrite.*` à identidade de CI.

## Escopo

- Ambiente: somente DEV.
- Host físico: somente `NOTERI`, via runner `[self-hosted, Windows, X64, noteri, reqsys-dev]`.
- Entrada operacional: somente o comando literal `/reqsys run teams-bot-dev-identity-bootstrap` na issue #1705 pelo owner autorizado.
- Execução administrativa: `Session Launcher` seguido de `Owner Risk3 Gateway`, com `action_id` e `scope` fixos e autorização local temporária.
- Bootstrap canônico: `scripts/bootstrap_teams_bot_dev_identity.py`.
- Armazenamento de credencial: Azure Key Vault já definido pelo bootstrap canônico; valor do segredo nunca é exposto.

## Fora de escopo

- TEST, HML, STG e PROD.
- Criação ou rotação arbitrária de credenciais.
- Concessão de `Application.ReadWrite.*` ao CI.
- Comando, tenant, app, vault, secret name ou workflow arbitrários fornecidos pelo comentário.
- Shell irrestrito, GUI ou bypass de governança.

## Fluxo

1. O Authorized Actions Gateway valida issue, ator e comando literal.
2. O workflow despachado executa somente no Noteri allowlisted.
3. O Session Launcher materializa sessão governada no SHA exato da `main`.
4. A variável não secreta `CCP_AZURE_TENANT_ID` define o tenant esperado e o runner falha fechado se estiver ausente ou inválido.
5. Uma autorização Owner Risk3 exata é instalada por no máximo 30 minutos.
6. O runner executa:
   - dry-run do bootstrap;
   - aplicação idempotente;
   - novo dry-run como leitura independente.
7. A evidência final registra apenas estado sanitizado, incluindo App ID e flags de criação, sem valor do segredo.
8. A autorização Risk3 temporária é removida em `always()`.

## Critérios de aceite

1. O comando aceito pelo gateway é exatamente `/reqsys run teams-bot-dev-identity-bootstrap`, restrito à issue #1705 e ao owner autorizado.
2. O workflow executa a etapa administrativa somente no host `NOTERI` e somente após `SESSION_LAUNCH_OK`, `state_validated=true` e SHA igual ao SHA despachado.
3. O workflow está explicitamente allowlisted em `.github/self-hosted-runner-policy.json` e o Self-Hosted Runner Governance Guard conclui com sucesso.
4. A mutação passa exclusivamente por `Owner Risk3 Gateway` usando `reqsys.teams-bot-dev-identity-bootstrap.dev` e `repo://ericson-j-santos/reqsys-v2-enterprise-real/environment/dev/teams-bot-identity`.
5. A autorização Risk3 expira em no máximo 30 minutos na execução normal e é removida mesmo se a execução falhar.
6. O tenant esperado é obtido de `CCP_AZURE_TENANT_ID`; nenhum token, senha, MFA ou client secret aparece na allowlist, comando, log ou artifact.
7. O bootstrap é idempotente: se App Registration, service principal e segredo governado já estiverem completos, a execução termina como `ALREADY_COMPLIANT` sem rotação desnecessária.
8. Após a aplicação, nova leitura independente confirma a mesma App ID, segredo existente/ativo e nenhuma ação pendente.
9. A evidência final contém `independent_readback=true`, `secret_value_exposed=false` e `production_touched=false`.
10. TEST/HML/STG/PROD permanecem intocados.
11. Ausência do runner, sessão Entra válida, tenant esperado, Key Vault ou permissão administrativa faz a execução falhar fechado.
12. Os testes de contrato do bootstrap, do gateway e da governança self-hosted permanecem verdes no mesmo SHA.
