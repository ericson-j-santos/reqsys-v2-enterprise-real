# Gate manual — reqsys-ollama-local-gateway

## Estado

Repositório **criado e acessível**: `ericson-j-santos/reqsys-ollama-local-gateway`

Pendência restante: publicar v0.2.0 (`POST /v1/chat`) via PR no repositório externo.

## Publicação

```bash
bash scripts/sincronizar_ollama_gateway_repo.sh
```

Requer permissão de escrita no repositório externo (owner ou token com `contents: write`).

## Integração ReqSys

Provider `ollama_gateway` integrado ao Codex governado. Configuração:

```env
CODEX_OLLAMA_GATEWAY_URL=http://localhost:8008
CODEX_OLLAMA_GATEWAY_API_KEY=placeholder-local-dev
```

## Critério de conclusão da issue #95

- [x] Repositório externo existe
- [x] Bootstrap v0.2.0 com `/v1/chat` no monólito ReqSys
- [x] Provider `ollama_gateway` no backend ReqSys
- [ ] PR mergeado no repositório externo (requer token com permissão de push)
