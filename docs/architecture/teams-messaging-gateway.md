# Teams Messaging Gateway

## Decisao

O ReqSys passa a expor um gateway unico para mensageria Teams em `/v1/teams-gateway`.
O gateway centraliza roteamento, auditoria, fallback e mensagens de erro sobre as
limitacoes reais do Microsoft Graph.

## Rotas suportadas

| Canal | Uso recomendado | Usuario logado | Observacao |
|---|---|---:|---|
| `graph_delegado` | Chats humanos 1:1/grupo | Sim | Usa `usuario_access_token` MSAL com `ChatMessage.Send` e `Chat.ReadWrite`. |
| `webhook` | Alertas automaticos, canal, eventos operacionais | Nao | Melhor caminho para automacao backend sem usuario logado. |
| `graph_app_only` | Cenarios onde app/bot e participante | Nao | Nao resolve chat humano-humano; usar apenas explicitamente. |
| `bot` | Servico completo sem usuario logado | Nao | Rota futura para Teams App/Bot instalado. |

## Contrato principal

`POST /v1/teams-gateway/messages`

```json
{
  "destino_tipo": "chat",
  "modo": "auto",
  "destino_id": "chat-id",
  "texto": "Mensagem ReqSys",
  "usuario_access_token": "token-delegado-opcional",
  "permitir_fallback": true,
  "metadata": {
    "titulo": "ReqSys"
  }
}
```

Resposta padronizada:

```json
{
  "entregue": true,
  "canal_usado": "graph_delegado",
  "destino_tipo": "chat",
  "correlation_id": "uuid",
  "fallback_usado": false,
  "message_id": "msg-id"
}
```

## Politica padrao ouro

- Chat humano sem `usuario_access_token` nao tenta burlar o Graph; retorna erro claro.
- Automacao backend deve preferir `webhook` ou, no futuro, `bot`.
- `auto` usa Graph delegado quando ha token, webhook quando o destino e operacional,
  e bloqueia quando nao ha rota segura.
- Toda tentativa registra `teams_gateway` no historico de integracoes.
- Webhook tem retry e circuit breaker proprio.
- Endpoints antigos de `hub_lowcode` continuam compativeis.

## Endpoints

- `GET /v1/teams-gateway/status`
- `POST /v1/teams-gateway/routes`
- `POST /v1/teams-gateway/messages`
- `POST /v1/teams-gateway/messages/delegated`
- `POST /v1/teams-gateway/messages/webhook`
