# Gate — reqsys-ollama-local-gateway

## Estado: resolvido no ReqSys

| Item | Status |
|---|---|
| Repositório externo existe | ✅ `ericson-j-santos/reqsys-ollama-local-gateway` |
| Bootstrap v0.2.0 com `/v1/chat` | ✅ `docs/ollama-local-gateway/bootstrap-files/` |
| Provider `ollama_gateway` no ReqSys | ✅ |
| Stack local one-command | ✅ `bash scripts/iniciar_codex_local.sh` |
| CI validação bootstrap | ✅ `.github/workflows/ollama-gateway-bootstrap.yml` |

## Publicação no repo externo (automatizado)

### Push model (ReqSys → repo externo)

O workflow **Ollama Gateway Bootstrap** publica o bootstrap na `main` do repo externo quando:

- há push na `main` do ReqSys alterando `docs/ollama-local-gateway/`; ou
- é disparado manualmente (`workflow_dispatch`).

Token (uma das opções, em ordem de preferência):

1. `OLLAMA_GATEWAY_SYNC_TOKEN` — PAT dedicado com `contents:write` no repo externo
2. `GH_PAT_ACTIONS` — secret já usado por outros workflows do ReqSys (fallback canônico)

Disparo one-command:

```bash
bash scripts/configurar_ollama_gateway_sync.sh
```

Ou localmente com PAT:

```bash
GH_TOKEN=<seu-pat> bash scripts/sincronizar_ollama_gateway_repo.sh
```

### Pull model (repo externo ← ReqSys)

Após a primeira sync, o workflow `sync-from-reqsys.yml` (incluído no bootstrap) espelha o ReqSys a cada 6h ou sob demanda, usando apenas o `GITHUB_TOKEN` do próprio repo externo.

## Critério de conclusão issue #95

- [x] Repositório externo existe
- [x] Bootstrap v0.2.0 no monólito ReqSys
- [x] Provider `ollama_gateway` integrado
- [x] Uso local sem dependência do push externo
- [x] Automação de sync (push + pull model)
