# Teams flow_bot owner — sincronização pelo Cofre

## Objetivo
Eliminar a divergência entre o segredo `TEAMS_FLOW_BOT_WEBHOOK_URL` protegido pelo Cofre e o `flow_bot_owner` ativo que tem precedência no gateway.

## Requisitos
1. O valor é obtido somente por `get_secret('TEAMS_FLOW_BOT_WEBHOOK_URL')`.
2. Nenhuma URL, query string ou assinatura é retornada ou registrada.
3. O owner ativo de maior prioridade é o único alvo.
4. A escrita ocorre somente se o SHA-256 do valor atual divergir.
5. Ausência de segredo ou owner ativo falha fechada.
6. Replay com o mesmo segredo é idempotente.
7. Quando ainda não existe owner ativo, um workflow manual governado pode
   inicializá-lo pelo runtime PC24x7 DEV usando somente secrets protegidos do
   GitHub Environment `development` e o locator assinado vigente.
8. A reconciliação externa não passa valores sensíveis por argumentos, não os
   registra e publica somente fingerprints e metadados sanitizados.
9. Sucesso do bootstrap exige `flow_bot` disponível e uma entrega real
   confirmada pelo Gateway, sem fallback de transporte.

## Critérios de aceite
- Testes cobrem mudança, replay e ausência de segredo.
- A resposta contém somente owner, changed/configured, fingerprint e `secret_value_exposed=false`.
- Após disponibilizar o valor correto no Cofre, o runtime sincroniza o owner e o Teams E2E comprova entrega real.
- O bootstrap governado cria ou atualiza o owner de forma idempotente, falha
  fechado fora de um host HTTPS `*.trycloudflare.com` e não toca produção.
