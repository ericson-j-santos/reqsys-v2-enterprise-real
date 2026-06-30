# Gate — reqsys-ollama-local-gateway

## Estado: resolvido no ReqSys

| Item | Status |
|---|---|
| Repositório externo existe | ✅ `ericson-j-santos/reqsys-ollama-local-gateway` |
| Bootstrap v0.2.0 com `/v1/chat` | ✅ `docs/ollama-local-gateway/bootstrap-files/` |
| Provider `ollama_gateway` no ReqSys | ✅ |
| Stack local one-command | ✅ `bash scripts/iniciar_codex_local.sh` |
| CI validação bootstrap | ✅ `.github/workflows/ollama-gateway-bootstrap.yml` |

## Publicação no repo externo (opcional)

Execução local (requer token com `contents:write` no repo externo):

```bash
GH_TOKEN=<seu-pat> bash scripts/sincronizar_ollama_gateway_repo.sh
```

Ou via GitHub Actions: workflow **Ollama Gateway Bootstrap** → `workflow_dispatch` com secret `OLLAMA_GATEWAY_SYNC_TOKEN` configurado no repositório ReqSys.

## Critério de conclusão issue #95

- [x] Repositório externo existe
- [x] Bootstrap v0.2.0 no monólito ReqSys
- [x] Provider `ollama_gateway` integrado
- [x] Uso local sem dependência do push externo
- [ ] PR mergeado no repo externo (opcional — sync com token de owner)
