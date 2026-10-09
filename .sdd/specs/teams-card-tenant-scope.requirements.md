# Requisitos — teams-card-tenant-scope

## Contexto

Uma Activity do Microsoft Teams identifica o tenant Entra que originou a mensagem. Uma
conversa de IA do ReqSys possui um tenant logico proprio, como `reqsys-dev`. Esses dois
identificadores pertencem a escopos diferentes e nao podem ser comparados como se fossem o
mesmo tenant.

## Requisito 1 — Continuar a conversa correta

Como usuario de aceite no Teams, quero submeter uma mensagem nao vazia no Adaptive Card para
que o ReqSys acrescente o novo turno ao `conversation_id` exibido no cartao.

### Critérios de aceite

1. DADA uma Activity autenticada pelo Bot Framework com tenant Entra valido, QUANDO o cartao
   referencia uma conversa cujo tenant logico e diferente, ENTAO a conversa DEVE ser buscada
   pelo `conversation_id`, sem aplicar o tenant Entra como tenant logico.
2. O remetente DEVE continuar correspondendo ao `teams_destino_id` associado a conversa.
3. O novo turno DEVE preservar `activity.id` como chave de idempotencia e `origem=teams`.
4. Uma conversa inexistente DEVE continuar retornando 404 e um remetente nao associado DEVE
   continuar retornando 403.

## Requisito 2 — Nao reduzir os controles do canal

Como responsavel pela seguranca do gateway, quero corrigir o escopo da consulta sem ampliar a
autorizacao do endpoint.

### Critérios de aceite

1. O endpoint DEVE continuar exigindo JWT valido do Bot Framework.
2. A entrega da resposta DEVE continuar usando a `conversationReference` governada pelo bot.
3. A correcao NAO DEVE alterar TEST ou PROD, credenciais, provedores de IA ou regras de
   readiness.

## Evidencia esperada

- Testes focados do endpoint, transporte Bot e readiness verdes.
- Prova fisica pos-merge em DEV com o mesmo `conversation_id`, evento
  `AI_CONVERSATION_TEAMS_REPLY_COMPLETED`, hashes de conteudo e ausencia de vazamento de
  segredo.
