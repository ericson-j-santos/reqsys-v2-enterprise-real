# ADR-001 — Provider local Ollama via Gateway

## Status

Aceito.

## Contexto

O ReqSys Codex precisa consumir modelos Ollama locais sem expor a porta nativa `11434` nem acoplar o monólito ao runtime Ollama.

## Decisão

Expor `POST /v1/chat` como contrato HTTP governado, consumido pelo provider `ollama_gateway` do ReqSys.

## Consequências

- O gateway isola Ollama e pode evoluir independentemente.
- O ReqSys mantém autenticação JWT, rate limit e auditoria corporativa.
- Chamadas reais ao Ollama ficam restritas ao gateway.

## Guard rails

- `X-API-Key` obrigatória quando `REQSYS_AUTH_REQUIRED=true`.
- CORS sem wildcard em produção.
- Logs com `correlation_id` e sem PII.
- Nenhuma chamada real ao Ollama nos testes unitários.
