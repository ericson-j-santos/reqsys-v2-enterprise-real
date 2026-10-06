# Cofre bootstrap — credencial administrativa local

## Objetivo
Eliminar o GitHub Secret COFRE_ADMIN_JWT do bootstrap S2S. O JWT humano deve ser obtido somente do Cofre DEV como human_admin_jwt:dev, validado por expiração e usado apenas no mint.

## Requisitos
1. O workflow não injeta COFRE_ADMIN_JWT.
2. O script mantém fallback para read_admin_jwt quando admin_jwt não é fornecido.
3. read_admin_jwt usa human_admin_jwt:dev e rejeita JWT expirado ou próximo da expiração.
4. Nenhum valor secreto é publicado.
5. O bootstrap no PC24x7 lê `human_admin_jwt:dev` e executa o mint dentro do container DEV; o JWT administrativo nunca deixa o container e não depende de `VAULT_API_TOKEN` global ou GitHub Secret.
6. Ausência, payload inválido ou expiração da credencial local falha fechado.

## Critérios de aceite
- Teste impede reintrodução de COFRE_ADMIN_JWT no workflow.
- Script comprova lookup de human_admin_jwt:dev e validação de expiração.
- HTTP 401 de mint não é mascarado.
- Produção não é tocada.
- Somente o novo token S2S destinado ao Key Vault pode retornar pelo pipe local.
