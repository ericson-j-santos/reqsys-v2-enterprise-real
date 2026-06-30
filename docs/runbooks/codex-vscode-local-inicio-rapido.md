# Runbook — Codex VS Code Local (Ollama + Continue)

## Objetivo

Colocar em operação o assistente de codificação gratuito/local integrado ao ReqSys, usando VS Code + extensão Continue + Ollama.

## Início rápido (1 comando)

```bash
docker compose -f infra/codex-local/docker-compose.ollama.yml up -d
ollama pull qwen2.5-coder:7b
bash scripts/iniciar_codex_local.sh
```

Sobe automaticamente:

| Serviço | Porta | Função |
|---|---|---|
| Ollama | `11434` | Modelos locais |
| Gateway | `8008` | Provider `ollama_gateway` |
| Backend ReqSys | `8000` | API Codex governada |
| Frontend | `5173` | Tela `/codex` |

Acesse `http://127.0.0.1:5173/codex` (login demo com e-mail).

## VS Code + Continue

```bash
mkdir -p ~/.continue
cp infra/codex-local/continue/config.yaml ~/.continue/config.yaml
```

Use `Ctrl+L` (chat) com **Qwen2.5 Coder**.

## Sync repo externo (opcional)

```bash
GH_TOKEN=<pat-com-write> bash scripts/sincronizar_ollama_gateway_repo.sh
```

Ou workflow **Ollama Gateway Bootstrap** com secret `OLLAMA_GATEWAY_SYNC_TOKEN`.

## Validação

```bash
python3 tools/codex-local-online/validate.py
cd docs/ollama-local-gateway/bootstrap-files && pip install -e .[dev] && pytest -q
cd backend && pytest tests/test_codex_governado*.py -q
```

## Referências

- `docs/codex-local/DECISAO_GATEWAY_OLLAMA_PROVIDER.md`
- `docs/ollama-local-gateway/MANUAL_GATE_CREATE_REPOSITORY.md`
