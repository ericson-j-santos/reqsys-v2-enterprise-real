# Runbook — Publicar repositório independente do Ollama Local Gateway

## Objetivo

Manter sincronizado o repositório `ericson-j-santos/reqsys-ollama-local-gateway` com o bootstrap canônico do ReqSys.

## Estado atual

| Item | Status |
|---|---|
| Repositório externo | ✅ Existe |
| Bootstrap v0.2.0 no ReqSys | ✅ `docs/ollama-local-gateway/bootstrap-files/` |
| Uso local sem sync externo | ✅ `bash scripts/iniciar_codex_local.sh` |
| Provider `ollama_gateway` | ✅ Integrado |

## Sync para repo externo

```bash
GH_TOKEN=<pat-com-write-no-repo-externo> bash scripts/sincronizar_ollama_gateway_repo.sh
```

Ou GitHub Actions → **Ollama Gateway Bootstrap** → `workflow_dispatch` (secret `OLLAMA_GATEWAY_SYNC_TOKEN`).

## Arquitetura

O gateway não substitui o Codex no ReqSys. É provider local via HTTP (`POST /v1/chat`).

```
ReqSys /codex → ollama_gateway → Gateway :8008 → Ollama :11434
```

## Referências

- `docs/ollama-local-gateway/MANUAL_GATE_CREATE_REPOSITORY.md`
- `docs/codex-local/DECISAO_GATEWAY_OLLAMA_PROVIDER.md`
- Issue #95
