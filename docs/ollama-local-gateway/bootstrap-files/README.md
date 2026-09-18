# ReqSys Ollama Local Gateway

Gateway local governado para integração do ReqSys com providers locais compatíveis com Ollama.

## Objetivo

Fornecer uma camada isolada, auditável e segura para chamadas locais de IA, mantendo separação entre o repositório principal ReqSys e o runtime/provider local.

## Escopo inicial

- Healthcheck operacional.
- Configuração por variáveis de ambiente.
- Contratos JSON versionáveis.
- Logs estruturados com `correlation_id`.
- Guardrails para evitar exposição de secrets e PII.

## Fora do escopo inicial

- Deploy em produção sem aprovação humana.
- Exposição pública sem autenticação.
- Administração remota de modelos sem RBAC.
- Persistência de prompts sensíveis.

## Execução local

```bash
pip install -e .[dev]
uvicorn reqsys_ollama_gateway.main:app --host 0.0.0.0 --port 8008
```

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | Healthcheck com `correlation_id` |
| POST | `/v1/chat` | Chat governado consumido pelo ReqSys (`ollama_gateway`) |

## Variáveis esperadas

| Variável | Finalidade |
|---|---|
| `REQSYS_ENV` | Ambiente: `dev`, `hml` ou `prod` |
| `REQSYS_OLLAMA_BASE_URL` | URL base local do Ollama |
| `REQSYS_AUTH_REQUIRED` | Exigir autenticação |
| `REQSYS_ALLOWED_ORIGINS` | Origens permitidas, sem wildcard em produção |
| `REQSYS_GATEWAY_API_KEY` | Chave para `X-API-Key` |
| `REQSYS_OLLAMA_TIMEOUT_SECONDS` | Timeout das chamadas ao Ollama |

## Segurança

Consulte `SECURITY.md` e `docs/SECURITY_GUARDRAILS.md`.
