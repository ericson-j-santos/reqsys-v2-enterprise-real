# Fabric OIDC Read-only Probe — Requisitos

## Objetivo

Validar, sem segredo estático, se a identidade Azure OIDC governada do ReqSys consegue localizar workspaces Microsoft Fabric/Power BI e a App Registration `ReqSys ALM Pipeline`.

## Classificação

`gap_fix`.

## Requisitos

1. O probe real deve executar somente por `workflow_dispatch`.
2. A autenticação deve usar `azure/login` com `id-token: write` e o GitHub Environment `development`.
3. Nenhum client secret, token bearer, senha ou PAT pode ser recebido, impresso ou persistido.
4. As chamadas Fabric, Power BI e Microsoft Graph devem ser somente leitura.
5. A evidência deve registrar tenant, status HTTP, workspaces visíveis e aplicações localizadas, sem material de autenticação.
6. O workflow deve falhar fechado se a autenticação OIDC ou o tenant esperado não forem comprovados.
7. Deve existir controle negativo automatizado proibindo métodos HTTP mutadores e comandos de alteração de RBAC/credencial.
8. A execução não pode tocar HML, STG ou PROD; trata-se somente de descoberta em `development`.

## Critérios de aceite

- contrato local verde;
- CI e gates SDD verdes no HEAD exato;
- execução `workflow_dispatch` na `main` com artifact sanitizado;
- `secret_value_exposed=false`;
- `mutations_performed=false`.
