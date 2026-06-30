# Runbook — Codex VS Code Local (Ollama + Continue)

## Objetivo

Colocar em operação o assistente de codificação gratuito/local integrado ao ReqSys.

## Início rápido

```bash
docker compose -f infra/codex-local/docker-compose.ollama.yml up -d
ollama pull qwen2.5-coder:7b
bash scripts/iniciar_codex_local.sh
```

| Serviço | Porta | Função |
|---|---|---|
| Ollama | `11434` | Modelos locais |
| Gateway | `8008` | Provider `ollama_gateway` |
| Backend | `8000` | API Codex governada |
| Frontend | `5173` | Tela `/codex` |

Acesse `http://127.0.0.1:5173/codex` (login demo com e-mail).

## VS Code + Continue

```bash
mkdir -p ~/.continue
cp infra/codex-local/continue/config.yaml ~/.continue/config.yaml
```

## Sync repo externo (automatizado)

O CI usa `GH_PAT_ACTIONS` automaticamente (fallback quando `OLLAMA_GATEWAY_SYNC_TOKEN` não existe).

```bash
# Dispara sync imediato (usa GH_PAT_ACTIONS no CI)
bash scripts/configurar_ollama_gateway_sync.sh
```

Opcional — PAT dedicado:

```bash
OLLAMA_GATEWAY_SYNC_TOKEN=<pat> bash scripts/configurar_ollama_gateway_sync.sh
```

Após a primeira publicação, o repo externo mantém espelho via workflow `sync-from-reqsys.yml` (a cada 6h).

O sync push também roda em alterações na `main` em `docs/ollama-local-gateway/`.

## Validação

```bash
python3 tools/codex-local-online/validate.py
cd docs/ollama-local-gateway/bootstrap-files && pip install -e .[dev] && pytest -q
cd backend && pytest tests/test_codex_governado*.py -q
```

## Referências

- `docs/codex-local/DECISAO_GATEWAY_OLLAMA_PROVIDER.md`
- `docs/ollama-local-gateway/MANUAL_GATE_CREATE_REPOSITORY.md`
