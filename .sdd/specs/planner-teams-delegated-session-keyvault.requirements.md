# Planner → Teams DEV — identidade delegada e sessão governada

## Requisitos
1. O aceite DEV deve restaurar e persistir a sessão Microsoft por Azure Key Vault usando OIDC do Credential Control Plane.
2. A sessão persistida deve conter somente um RefreshToken MSAL mínimo; cookies, access tokens, ID tokens e device code devem ser descartados.
3. A identidade dedicada deve ser single-tenant e cliente público, sem client secret.
4. As permissões delegadas ficam limitadas a leitura de ambientes/conexões do Power Platform e gestão de flows necessária ao aceite.
5. O bootstrap não pode conceder consentimento administrativo automaticamente nem usar Application.ReadWrite.All.
6. O estado legado WSJF_MSAL_STORAGE_STATE_B64 é somente uma ponte de migração enquanto a identidade dedicada ainda não existir.
7. Quando a identidade dedicada existir, uma sessão pertencente a outro client ID deve ser descartada em vez de reutilizada.
8. O device code deve continuar sendo renovado automaticamente no mesmo run; interação humana só permanece para login, MFA ou consentimento exigidos pelo Microsoft Entra.

## Critérios de aceite (Acceptance Criteria)
1. Testes comprovam que o valor persistido no Key Vault elimina material de navegador e mantém somente um refresh token.
2. Persistência no Key Vault usa arquivo temporário protegido e não coloca o refresh token na linha de comando.
3. Testes comprovam rollback da App Registration quando o bootstrap recém-criado falha antes de concluir.
4. O workflow de bootstrap é manual, main-only, usa OIDC e não possui client secret.
5. O workflow de aceite usa OIDC, restaura e persiste a sessão no Key Vault e não decodifica diretamente o secret legado.
6. O primeiro login da identidade dedicada funciona mesmo quando ainda não existe refresh token.
7. O catálogo do Credential Control Plane registra client ID e sessão delegada sem valores secretos.
8. O Pre-PR Readiness deve retornar READY_FOR_PR=passed no HEAD exato, com behind_by=0, antes de abrir PR.
9. Após integração e bootstrap administrativo, E2E real deve comprovar uma primeira autorização persistida e uma execução subsequente que reutilize a sessão sem novo código.
