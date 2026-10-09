# Requisitos — conversa bidirecional pelo Teams Bot

## Contexto

O webhook do Azure Bot autenticava a `Activity` e atualizava a
`conversationReference`, mas uma mensagem de texto livre terminava em HTTP 200
sem executar a Central de Conversas de IA. O envio proativo funcionava, porém o
usuário não recebia resposta ao conversar normalmente com o bot.

## Requisitos funcionais

1. Os endpoints `/v1/teams-gateway/bot/messages` e
   `/v1/teams-gateway/ai-conversations/bot/messages` DEVEM aceitar mensagens de
   texto autenticadas pelo Bot Framework e encaminhá-las para a mesma camada de
   processamento conversacional.
2. O webhook DEVE responder ao Bot Framework antes da execução do provedor de IA,
   usando uma sessão de banco própria no processamento em segundo plano.
3. Uma mensagem livre DEVE reutilizar a conversa aberta mais recente do mesmo
   usuário AAD e tenant; na ausência dela, DEVE criar uma nova conversa vinculada
   ao remetente.
4. Somente um provedor configurado e permitido pela política corporativa PODE ser
   selecionado. O provedor local configurado DEVE permanecer disponível como
   fallback governado.
5. O `activity.id` DEVE ser usado como chave de idempotência. Um retry da mesma
   Activity não pode executar novamente o turno nem duplicar a resposta.
6. A resposta DEVE ser enviada ao mesmo chat pelo Bot Framework e vinculada à
   Activity de entrada quando houver `activity.id`.
7. O fluxo existente de `Action.Submit` dos Adaptive Cards DEVE continuar exigindo
   que o usuário AAD esteja associado à conversa informada.
8. Falhas internas ou do provedor NÃO DEVEM expor exceções, tokens ou segredos. O
   usuário deve receber apenas uma mensagem de falha sanitizada.

## Segurança e limites

- O JWT do Bot Framework continua obrigatório e validado antes de qualquer escrita.
- Mensagens sem identidade AAD não iniciam processamento de IA.
- A correção é restrita a DEV/PC24x7 e não promove TEST ou PROD.
- Logs e artifacts devem conter apenas categorias de falha e identificadores de
  correlação não secretos.

## Critérios de aceite

1. Lint e testes focados do Bot ficam verdes.
2. A suíte completa do backend fica verde.
3. O SDD gate reconhece este spec e seu arquivo de requisitos no mesmo SHA.
4. Após merge e reconciliação no PC24x7, uma mensagem humana nova recebe resposta
   visível no mesmo chat do Teams.
5. A repetição da mesma Activity não gera um segundo turno.
6. Nenhum segredo é exposto e produção permanece intocada.

## Rollback

Reverter o commit remove o processamento de mensagens livres e restaura o
comportamento anterior de apenas persistir a `conversationReference`. O rollback
não remove conversas existentes, não altera credenciais e não toca produção.
