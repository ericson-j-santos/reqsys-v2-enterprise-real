# Cofre bootstrap — credencial administrativa local

## Objetivo
Eliminar o GitHub Secret COFRE_ADMIN_JWT do bootstrap S2S. No PC24x7, o runtime DEV emite um JWT administrativo de cinco minutos usando sua configuração protegida, consome-o localmente no mint e nunca o exporta.

## Requisitos
1. O workflow não injeta COFRE_ADMIN_JWT.
2. O script mantém fallback para read_admin_jwt quando admin_jwt não é fornecido.
3. read_admin_jwt usa human_admin_jwt:dev e rejeita JWT expirado ou próximo da expiração.
4. Nenhum valor secreto é publicado.
5. O bootstrap no PC24x7 emite o JWT administrativo efêmero e executa o mint dentro do container DEV; o JWT nunca deixa o container e não depende de `VAULT_API_TOKEN` global ou GitHub Secret.
6. O alvo permanece fixado ao container DEV canônico; qualquer outro container ou ambiente falha fechado.

## Critérios de aceite
- Teste impede reintrodução de COFRE_ADMIN_JWT no workflow.
- Script comprova emissão efêmera com TTL de cinco minutos e consumo pelo endpoint loopback do runtime.
- HTTP 401 de mint não é mascarado.
- Produção não é tocada.
- Somente o novo token S2S destinado ao Key Vault pode retornar pelo pipe local.
