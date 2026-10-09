# Requisitos — continuidade operacional Teams no PC24x7

## Objetivo

Remover dependências executáveis do Fly.io retirado e fazer os controles operacionais de
DEV observarem o runtime PC24x7 vigente por meio do locator público assinado.

## Critérios de aceite

1. O probe de políticas de destinatários DEVE resolver o runtime DEV pelo locator assinado,
   validar o contrato do locator em modo fail-closed e não usar fallback para Fly.io.
2. O smoke agendado do Control Center DEVE executar somente contra DEV/PC24x7. HML e PROD
   permanecem disponíveis apenas por dispatch explícito e por URL provider-neutral configurada.
3. O workflow desativado de homologação do Merge Console no Fly DEV DEVE ser removido.
4. O readiness do bot DEVE considerar `blocked` uma `conversationReference` cujo `bot_id` ou
   `tenant_id` não pertença ao bot configurado, sem expor esses identificadores na resposta. O
   prefixo de channel account `28:` definido pelo Teams DEVE ser normalizado antes da comparação
   exata com o Microsoft App ID; qualquer outro identificador continua bloqueado.
5. Uma referência válida e pertencente ao bot vigente DEVE preservar o resultado `ready`.
6. Nenhuma mensagem real, promoção ou alteração de produção pode ocorrer durante os testes.
7. A validação posterior do ruleset DEVE comparar os nomes acentuados dos checks sem depender
   da codificação do arquivo temporário criado pelo Windows PowerShell.
8. No gateway público PC24x7, health e autenticação DEV DEVEM usar o prefixo `/api`, enquanto
   as rotas públicas protegidas do Teams permanecem em `/v1/teams-gateway/`.
9. O Adaptive Card bidirecional DEVE bloquear submissão sem mensagem no cliente. Caso um cliente
   ainda envie o payload vazio, o endpoint do Bot Framework DEVE responder HTTP 200, registrar a
   rejeição e não chamar o provedor de IA, evitando que o Teams apresente falso erro de aplicativo.
10. O replay de uma mesma chave idempotente na rota `/reply` ou do mesmo `activity.id` no submit
    do Bot Framework DEVE retornar `duplicate=true` sem nova entrega direta, novo Adaptive Card ou
    novo item de fila Teams.
11. O Bot Connector DEVE aceitar qualquer resposta HTTP 2xx sem corpo como bem-sucedida,
    sem tentar interpretar JSON e sem acionar fallback por erro de parsing. O status HTTP
    aceito DEVE ser preservado na evidência. Respostas com corpo não vazio malformado e
    respostas HTTP de erro continuam bloqueadas.
12. O processamento assíncrono de mensagens Teams DEVE registrar sucesso ou falha com latência,
    estado de entrega e categoria técnica sanitizada, sem persistir texto da mensagem, resposta do
    modelo, identidade do usuário, token ou detalhe da exceção.

## Rollback

Reverter o commit restaura os workflows anteriores e remove o novo bloqueio de propriedade.
Esse rollback não recria infraestrutura Fly.io nem altera dados do runtime.
