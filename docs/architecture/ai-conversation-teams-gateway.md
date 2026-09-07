# Central de Conversas de IA + Microsoft Teams

## Objetivo

Permitir que uma conversa gerenciada pelo ReqSys continue entre dispositivos sem depender da interface de um provedor específico. Quando uma resposta de IA termina, o ReqSys entrega um Adaptive Card no Teams. A resposta digitada no cartão volta ao mesmo `conversation_id`, é enviada ao mesmo provedor/modelo e gera um novo cartão.

## Escopo deste incremento

Provedores suportados pelo adaptador atual:

- OpenAI
- Claude
- Gemini
- Groq
- Ollama

O histórico autoritativo fica no ReqSys em `ai_conversations` e `ai_conversation_messages`. A continuidade não depende do computador em que o primeiro turno foi iniciado.

## Fluxo gerenciado

```text
cliente/automação
    -> POST /v1/teams-gateway/ai-conversations
    -> AIConversation + AIConversationMessage
    -> LLMGateway
    -> resposta persistida
    -> Azure Bot / Bot Framework
    -> Adaptive Card no Teams
    -> Action.Submit
    -> /v1/teams-gateway/ai-conversations/bot/messages
    -> mesmo conversation_id
    -> próximo turno
```

## Contratos HTTP

### Criar conversa e executar primeiro turno

`POST /v1/teams-gateway/ai-conversations`

Exemplo:

```json
{
  "provider": "openai",
  "model": "gpt-5.6",
  "mensagem": "Analise o estado atual desta demanda.",
  "titulo": "Demanda ReqSys",
  "idempotency_key": "req-123-turn-1",
  "teams_destino_tipo": "chat_1a1",
  "teams_destino_id": "<AAD_OBJECT_ID>",
  "teams_modo": "bot",
  "enviar_teams": true
}
```

A rota exige JWT administrativo ou `X-Service-Token` com escopo `teams_gateway:ai_conversations`.

### Continuar via API

`POST /v1/teams-gateway/ai-conversations/{conversation_id}/reply`

```json
{
  "mensagem": "Continue e corrija a causa raiz.",
  "idempotency_key": "turn-2",
  "origem": "api",
  "enviar_teams": true
}
```

### Receber a resposta do Adaptive Card

Configure o Messaging Endpoint do Azure Bot para:

```text
https://<HOST_REQSYS>/v1/teams-gateway/ai-conversations/bot/messages
```

O endpoint valida o JWT do Bot Framework. O cartão envia somente identificadores de roteamento; credenciais dos provedores permanecem no servidor.

### Consultar estado

`GET /v1/teams-gateway/ai-conversations/status`

Retorna somente indicadores booleanos de configuração dos provedores. Não retorna chaves ou segredos.

## Idempotência

Cada mensagem de usuário possui uma chave única por conversa. Respostas vindas do Teams usam `activity.id` do Bot Framework:

```text
teams-activity:<activity.id>
```

Se a mesma atividade for retransmitida, o provedor não é chamado novamente. Se a mesma chave for usada com conteúdo diferente, o ReqSys responde com conflito.

O conteúdo persistido recebe `content_sha256` para rastreabilidade.

## Entrega Teams

A preferência é o Azure Bot com Adaptive Card, porque ele permite fechar o ciclo bidirecional sem manter uma execução de Power Automate aguardando resposta.

Para o primeiro envio proativo, o bot precisa ter uma `conversationReference`. O usuário deve ter instalado/iniciado o bot pelo menos uma vez. O ReqSys já persiste essa referência.

Resolução do destinatário:

1. `teams_destino_id` informado na conversa;
2. `AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID` do ambiente;
3. única `conversationReference` Teams existente no banco.

Se houver mais de um usuário e nenhum destino explícito, o ReqSys não escolhe silenciosamente um destinatário.

Quando o cartão direto pelo bot não está disponível, a resposta cai na fila governada existente do Teams Gateway, preservando retentativas, DLQ e evidência operacional. Esse fallback é de notificação; a resposta bidirecional garantida requer o Bot Framework.

## Configuração por ambiente

Variáveis novas:

```text
AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID
AI_CONVERSATION_TIMEOUT_SECONDS
AI_CONVERSATION_MAX_CONTEXT_CHARS
AI_CONVERSATION_SYSTEM_PROMPT
AI_CONVERSATION_OPENAI_API_KEY
AI_CONVERSATION_CLAUDE_API_KEY
AI_CONVERSATION_GEMINI_API_KEY
AI_CONVERSATION_GROQ_API_KEY
AI_CONVERSATION_OLLAMA_BASE_URL
```

As chaves específicas são opcionais. Quando ausentes, o adaptador reutiliza as variáveis já reconhecidas pelo `LLMGateway` onde aplicável.

## Segurança

- Nenhuma chave de IA é enviada ao Teams.
- O endpoint do Bot valida a assinatura JWT do Bot Framework.
- A API administrativa exige JWT admin ou service token escopado.
- O destino Teams fica mascarado na fila existente.
- Metadados da fila passam pelo sanitizador existente.
- Reenvios são idempotentes.
- A seleção implícita de destinatário é recusada quando há ambiguidade.

## Limitação explícita

Este incremento garante continuidade para **conversas gerenciadas pela Central**. Ele não transforma, por si só, uma conversa iniciada diretamente na interface nativa do ChatGPT, Claude, Gemini ou outro aplicativo em uma conversa controlável por API.

Integrações futuras para chats nativos devem entrar como adaptadores observadores específicos por plataforma (plugin, extensão ou integração oficial). A ausência de uma API oficial de escrita de volta deve ser tratada como limitação do provedor, não contornada por automação frágil de tela.

## Critérios de aceite

1. Criar uma conversa com um provedor configurado.
2. Persistir mensagem do usuário e resposta do assistente.
3. Entregar um Adaptive Card no Teams contendo o `conversation_id`.
4. Digitar uma continuação no cartão e submeter.
5. Validar que o mesmo `conversation_id` recebeu o novo turno.
6. Validar que o histórico anterior foi enviado ao provedor.
7. Reenviar a mesma atividade do Teams e comprovar que não houve segunda chamada ao provedor.
8. Validar `correlation_id`, SHA-256 e evento de auditoria.

## Ativação humana mínima

Após merge/deploy em DEV:

1. No Azure Bot, alterar o **Messaging endpoint** para `/v1/teams-gateway/ai-conversations/bot/messages`.
2. Garantir `TEAMS_BOT_APP_ID`, `TEAMS_BOT_APP_TENANT_ID` e `TEAMS_BOT_SECRET` no ambiente.
3. Iniciar/instalar o bot uma vez no Teams para gravar a `conversationReference`.
4. Definir `AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID` quando houver mais de um usuário cadastrado.
5. Configurar ao menos um provedor de IA.
6. Executar o critério de aceite ponta a ponta em DEV antes de promover para TEST/PROD.
