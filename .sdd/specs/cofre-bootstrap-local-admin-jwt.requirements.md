# Cofre bootstrap — identidade de máquina local DEV

## Objetivo
Eliminar definitivamente a dependência de identidade administrativa humana no bootstrap S2S. No PC24x7, uma operação interna sem endpoint HTTP rotaciona apenas identidades de máquina DEV explicitamente autorizadas e entrega o novo token ao processo OIDC que o persiste no Key Vault.

## Requisitos
1. O workflow não injeta COFRE_ADMIN_JWT.
2. O script não lê `human_admin_jwt`, `COFRE_ADMIN_JWT` nem `VAULT_API_TOKEN` para provisionar o token S2S.
3. O bootstrap local não cria JWT administrativo e não chama a rota administrativa HTTP.
4. Nenhum valor secreto é publicado.
5. O bootstrap executa um comando interno dentro do container DEV, limitado a identidades `(label, scope)` allowlisted e validade máxima de 90 dias.
6. O alvo permanece fixado ao container DEV canônico; qualquer outro container ou ambiente falha fechado.
7. A rotação revoga tokens anteriores da mesma identidade e grava o novo hash e o evento de auditoria na mesma transação.
8. O token em claro existe apenas no pipe capturado pelo bootstrap e é persistido imediatamente no Key Vault pela identidade OIDC do workflow.
9. A renovação humana oferece Device Code Flow para login e MFA pelo celular, troca o ID token pelo JWT interno e grava diretamente `human_admin_jwt:{env}` no Cofre.
10. O fluxo pelo celular não imprime ID token, JWT interno nem device code opaco; somente a URL pública de verificação e o `user_code` temporário são exibidos.
11. Se houver cache MSAL local compatível, o utilitário tenta renovação silenciosa sem exibir o refresh token; `invalid_grant` falha fechado e exige nova prova humana.
12. Falhas transitórias 502/503 após a aprovação são retentadas mantendo tokens somente em memória.
13. A automação governada DEVE oferecer operações explícitas `status` e `renew` no runner PC24x7
    DEV. `status` publica somente validade e estado sanitizados; `renew` exige Device Code e MFA
    humano, grava o JWT diretamente no Cofre e comprova validade sem revelar credenciais.
14. A renovação humana não DEVE ser agendada nem executada silenciosamente em loop, pois o JWT
    administrativo é efêmero e não participa do bootstrap S2S normal.

## Critérios de aceite
- Teste impede reintrodução de COFRE_ADMIN_JWT no workflow.
- Testes impedem reintrodução de JWT humano ou chamada ao endpoint administrativo no bootstrap PC24x7.
- Staging, produção, identidades fora da allowlist e validade acima de 90 dias falham fechados.
- A rotação produz evento auditável sem registrar o valor do token.
- Produção não é tocada.
- Somente o novo token S2S destinado ao Key Vault pode retornar pelo pipe local.
- Testes cobrem espera, `slow_down`, recusa, expiração e ausência de tokens na saída do Device Code Flow.
- Testes cobrem renovação silenciosa, cache incompatível e recuperação transitória do gateway.
- Testes cobrem o probe local sanitizado, bloqueio fora de DEV e o workflow manual sem schedule.
