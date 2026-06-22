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
  "provider": "mock",
  "contexto": "Validar PR do ReqSys",
  "entrada": "Falha no CI de backend",
  "publicar_no_reqsys": false
}
```

## Criterios de aceite

- Endpoint exige JWT.
- Modo mock responde sem provedor externo.
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
