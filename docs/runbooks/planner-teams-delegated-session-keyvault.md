# Planner → Teams DEV — sessão delegada governada

## Estado alvo

O aceite Planner → Teams DEV usa uma App Registration dedicada, pública e single-tenant.
Ela não possui client secret. A sessão renovável fica no Azure Key Vault e o workflow lê
e grava o cofre por GitHub OIDC.

Referências no cofre:

- client ID: `reqsys-planner-teams-delegated-client-id-dev`;
- sessão: `reqsys-planner-teams-delegated-session-dev`.

A sessão persistida é reduzida a um único RefreshToken MSAL. Cookies, access tokens,
ID tokens e device code não são persistidos.

## Bootstrap administrativo único

O código automatiza a operação de ponta a ponta, inclusive concessão e revogação de
`Application.ReadWrite.OwnedBy` no menor intervalo possível:

`scripts/bootstrap_planner_teams_delegated_identity_temporary_permission.py`

O script exige uma sessão local Microsoft Entra já autenticada e uma confirmação literal.
Ele não recebe senha, MFA ou token por argumento. Também não concede
`Application.ReadWrite.All`, não cria client secret e não concede consentimento
administrativo.

Durante o intervalo temporário ele dispara, na `main` corrente, o workflow confiável:

`Planner Teams Delegated Identity Bootstrap DEV`

Esse workflow cria/revalida a identidade dedicada, grava apenas o client ID no Key Vault
e cria a FIC do GitHub Environment `reqsys-power-platform-dev`. A atribuição temporária é
revogada em `finally`, inclusive quando o workflow falha.

## Operação normal

Após o bootstrap:

1. o aceite autentica no Azure por OIDC;
2. restaura a sessão do Key Vault;
3. se o refresh token ainda for aceito, nenhuma ação humana é solicitada;
4. se o Microsoft Entra exigir nova autenticação, o device code é publicado no Summary;
5. códigos expirados são renovados automaticamente no mesmo run;
6. após login/MFA/consentimento, a sessão renovada é compactada e persistida no Key Vault;
7. o E2E Planner → Power Automate → Teams continua automaticamente.

O estado legado `WSJF_MSAL_STORAGE_STATE_B64` é somente uma ponte de migração enquanto a
identidade dedicada ainda não estiver materializada. Depois do cutover, uma sessão de outro
client ID é descartada em vez de reutilizada.

## Limites de automação

Login, MFA e consentimento exigidos pelo Microsoft Entra continuam decisões humanas. A
automação não tenta contornar políticas de acesso condicional nem fabricar consentimento
administrativo.

## Evidência mínima para concluir

- Pre-PR Readiness verde no SHA exato;
- bootstrap da identidade com `OwnedBy` temporário comprovadamente revogado;
- FIC do environment `reqsys-power-platform-dev` comprovada;
- client ID dedicado presente no Key Vault;
- primeira autorização da identidade dedicada persistida;
- execução posterior reutilizando a sessão sem novo código;
- E2E Planner → Power Automate → Teams verde;
- nenhum refresh token, device code, senha ou client secret em logs/artifacts.
