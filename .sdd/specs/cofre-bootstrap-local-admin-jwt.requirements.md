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

## Critérios de aceite
- Teste impede reintrodução de COFRE_ADMIN_JWT no workflow.
- Testes impedem reintrodução de JWT humano ou chamada ao endpoint administrativo no bootstrap PC24x7.
- Staging, produção, identidades fora da allowlist e validade acima de 90 dias falham fechados.
- A rotação produz evento auditável sem registrar o valor do token.
- Produção não é tocada.
- Somente o novo token S2S destinado ao Key Vault retorna pelo pipe local.
