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
  "provider": "gemini",
  "contexto": "Validar PR do ReqSys",
  "entrada": "Falha no CI de backend",
  "publicar_no_reqsys": false
}
```

## Arquitetura de providers LLM

As chamadas externas para LLM ficam centralizadas em `backend/app/services/llm_provider.py`.

Responsabilidades da porta comum:

- montar payload HTTP por provider;
- aplicar headers de autenticacao;
- usar timeout padrao;
- extrair texto de respostas OpenAI-compatible, Claude, Gemini, Ollama e gateway local.

Responsabilidades que permanecem nos servicos consumidores:

- regra de negocio;
- rate limit por produto;
- fallback especifico;
- auditoria e persistencia de dominio;
- mensagens de erro publicas da API existente.

## Provider Gemini para Hermes Agent

Configure no `.env` local ou no cofre do ambiente:

```env
GEMINI_API_KEY=sua-chave-gemini
GEMINI_MODEL=gemini-3.5-flash
```

Depois selecione `gemini` na tela Codex Governado ou envie `"provider": "gemini"` para `/v1/codex/analyze`.

Trate `GEMINI_API_KEY` como segredo: nao commite, nao publique em chat e rotacione a chave se ela tiver sido exposta.

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
- Provider `gemini` usa a API Gemini com chave em variavel de ambiente.
- Provider `groq` usa API compatível com OpenAI Chat Completions.
- Porta comum de LLM centraliza payload, headers, timeout e extração textual.
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
