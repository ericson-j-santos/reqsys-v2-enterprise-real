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

1. Configure o secret no ReqSys (uma vez):

```bash
gh secret set OLLAMA_GATEWAY_SYNC_TOKEN -R ericson-j-santos/reqsys-v2-enterprise-real
# Cole um PAT com contents:write no repo reqsys-ollama-local-gateway
```

2. Dispare o workflow:

```bash
gh workflow run ollama-gateway-bootstrap.yml -R ericson-j-santos/reqsys-v2-enterprise-real
```

O sync também roda automaticamente em push na `main` quando o bootstrap muda e o secret está configurado.

## Validação

```bash
python3 tools/codex-local-online/validate.py
cd docs/ollama-local-gateway/bootstrap-files && pip install -e .[dev] && pytest -q
cd backend && pytest tests/test_codex_governado*.py -q
```

## Referências

- `docs/codex-local/DECISAO_GATEWAY_OLLAMA_PROVIDER.md`
- `docs/ollama-local-gateway/MANUAL_GATE_CREATE_REPOSITORY.md`
