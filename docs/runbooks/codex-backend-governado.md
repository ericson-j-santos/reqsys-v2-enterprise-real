# Runbook — Backend governado do Codex Online

## Endpoint

```text
POST /v1/codex/analyze
GET  /v1/codex/status
```

## Fluxo operacional

1. Autenticar no ReqSys.
2. Obter JWT de sessao.
3. Abrir o Codex Online.
4. Informar endpoint `/v1/codex/analyze`.
5. Informar JWT.
6. Selecionar provider.
7. Executar analise.
8. Validar `correlation_id`, payload ReqSys e logs.

## Exemplo de requisicao

```json
{
  "provider": "groq",
  "contexto": "Validar PR do ReqSys",
  "entrada": "Falha no CI de backend",
  "publicar_no_reqsys": false
}
```

## Provider Groq/Llama gratuito

Configure no `.env` local:

```env
GROQ_API_KEY=sua-chave-groq
GROQ_MODEL=llama-3.3-70b-versatile
```

Depois selecione `groq` na tela Codex Governado ou envie `"provider": "groq"` para `/v1/codex/analyze`.

## Criterios de aceite

- Endpoint exige JWT.
- Modo mock responde sem provedor externo.
- Provider `groq` usa API compatível com OpenAI Chat Completions.
- Conteudo sensivel e bloqueado.
- Rate limit retorna HTTP 429.
- Resultado contem `correlation_id`.
- Payload ReqSys e gerado.

## Troubleshooting

| Sintoma | Causa | Acao |
|---|---|---|
| 401 | JWT ausente ou invalido | Refazer login |
| 400 | Conteudo bloqueado | Remover dado sensivel |
| 429 | Muitas chamadas | Aguardar Retry-After |
| 503/502 | Provider indisponivel | Usar mock ou revisar configuracao |
