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
- `TEAMS_BOT_APP_ID` pertence a App Registration dedicada e não pode reutilizar `AZURE_CLIENT_ID`/`ReqSys Enterprise`.
- O CI não recebe permissão `Application.ReadWrite.*` no Microsoft Graph para contornar bootstrap do Entra.
- `CCP_AZURE_CLIENT_ID_DEV` permanece restrito aos tokens Fly DEV já definidos no Credential Control Plane; ele não lê o segredo do bot.
- O bootstrap do bot usa a identidade mutadora apenas para ler os dois segredos de controle no Key Vault e configurar credenciais no app Fly DEV fixo. Esse caminho não executa deploy e não amplia os leitores HML/PROD.

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

## Ativação DEV governada

A ativação foi separada em duas fronteiras para preservar menor privilégio.

### 1. Ação humana única no Microsoft Entra

Uma conta autorizada executa localmente:

```bash
az login --tenant <TENANT_ID>

# opcional: descreve o que seria criado, sem tocar em Entra ou Key Vault
python scripts/bootstrap_teams_bot_dev_identity.py \
  --confirm CRIAR-IDENTIDADE-TEAMS-BOT-DEV \
  --tenant-id <TENANT_ID> \
  --dry-run

python scripts/bootstrap_teams_bot_dev_identity.py \
  --confirm CRIAR-IDENTIDADE-TEAMS-BOT-DEV \
  --tenant-id <TENANT_ID>
```

O script:

1. exige confirmação literal;
2. valida sessão, tenant e acesso ao cofre **antes** de qualquer mutação, para nunca deixar uma identidade criada sem o segredo governado;
3. cria ou valida exatamente uma App Registration `ReqSys Teams Bot DEV` do tipo `AzureADMyOrg`, recusando uma homônima com outro `signInAudience`;
4. cria o service principal quando ausente;
5. cria um client secret somente quando o segredo canônico ainda não existe;
6. grava o valor diretamente em `kv-reqsys-ccp/reqsys-teams-bot-dev-secret` com a tag `app-id`;
7. nunca imprime nem grava o valor do segredo em evidência local;
8. em falha, reverte o que criou nesta execução — revoga a credencial recém-emitida e remove a App Registration quando ela também foi criada aqui.

Pré-requisitos da conta humana: permissão para criar/gerir a App Registration e a role `Key Vault Secrets Officer` sobre `kv-reqsys-ccp`. A ausência do acesso ao cofre é detectada no início e aborta antes de criar qualquer identidade.

Não conceder `Application.ReadWrite.All` ou `Application.ReadWrite.OwnedBy` ao CI apenas para eliminar essa ação humana inicial.

### 2. Ativação automática pelo GitHub Actions

`Teams Bot DEV Provision` usa `CCP_AZURE_CLIENT_ID`, federado à `main`, e executa:

```text
Key Vault: identidade + secret do bot
        ↓
Key Vault: reqsys-fly-control-plane-org-token
        ↓
preflight somente leitura contra reqsys-api-dev
        ↓
Azure Bot F0 / SingleTenant
        ↓
Messaging endpoint exato
        ↓
canal Microsoft Teams
        ↓
pacote Teams com App ID real
        ↓
TEAMS_BOT_APP_ID
TEAMS_BOT_APP_TENANT_ID
TEAMS_BOT_SECRET
        ↓
reqsys-api-dev
        ↓
/health
```

O trust anchor Fly é usado somente neste bootstrap de credencial para o app fixo `reqsys-api-dev`; não executa `flyctl deploy`, não cria tokens sucessores e não substitui os readers de deploy do Credential Control Plane.

A retomada é automática: além de `push` e `workflow_dispatch`, o workflow roda de hora em hora. Enquanto o bootstrap humano não existir, a execução agendada encerra sem alterar nada e sem alarme falso; assim que o segredo aparece no Key Vault, a janela seguinte conclui o provisionamento sem novo merge e sem reexecução manual. Qualquer outro bloqueio continua vermelho em qualquer gatilho.

A execução é idempotente: quando o Azure Bot já existe, o workflow exige correspondência de App ID, endpoint e SKU antes de reutilizá-lo. Quando as três credenciais já estão no `reqsys-api-dev`, a regravação é ignorada para não reiniciar o app a cada janela; use `workflow_dispatch` com `force_runtime_sync` para forçar a ressincronização após uma rotação de segredo. Falhas antes do commit dos segredos Fly removem apenas recursos Azure criados pela própria execução. Depois do commit no Fly, a configuração é preservada para permitir reexecução e diagnóstico sem apagar um runtime parcialmente ativado.

### 3. Primeira interação Teams

Esta é a segunda fronteira humana. Ela **não** pode ser antecipada: o pacote só
existe depois que a etapa 2 gera o App ID real, e o conector Microsoft 365 em uso
não expõe operação de instalação de aplicativo Teams — os escopos delegados
concedidos são de leitura de chats/canais e não incluem
`TeamsAppInstallation.ReadWriteForUser`.

Identidade de aceite (resolvida via Microsoft Graph, não presumida):

| Campo | Valor |
| --- | --- |
| UPN | `ericsonjosedossantos@tieri659.onmicrosoft.com` |
| AAD object ID | `0099abe2-63d9-4855-b087-364d1fbc9c30` |
| Tenant | `6d09c88c-0617-490c-8329-305e577684bc` |

O tenant da conta de aceite é o mesmo alvo do bootstrap, o que é condição
necessária para instalar um bot `AzureADMyOrg`: uma conta de outro tenant não
enxergaria o aplicativo. O `AAD object ID` acima é o valor a usar em
`AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID` quando houver mais de um usuário
cadastrado.

Pré-requisito ainda não verificável por esta automação: o tenant precisa permitir
o upload de aplicativo personalizado (sideloading) para a conta de aceite. A
política vive no Teams admin center e sua leitura exige escopo administrativo que
o conector atual não possui — se a instalação for recusada, verificar essa
política antes de suspeitar do pacote.

Depois de Azure Bot + runtime DEV verdes:

1. instalar/iniciar o pacote gerado no escopo pessoal da conta de aceite acima;
2. enviar a primeira mensagem ao bot para gravar a `conversationReference`;
3. definir `AI_CONVERSATION_TEAMS_USER_AAD_OBJECT_ID` quando houver mais de um usuário cadastrado;
4. configurar ao menos um provedor de IA;
5. executar os oito critérios de aceite acima antes de qualquer promoção para TEST/PROD.
