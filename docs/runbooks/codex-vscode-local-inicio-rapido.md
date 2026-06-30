# Runbook — Codex VS Code Local (Ollama + Continue)

## Objetivo

Colocar em operação o assistente de codificação gratuito/local integrado ao ReqSys, usando VS Code + extensão Continue + Ollama.

## Pré-requisitos

| Item | Versão mínima |
| --- | --- |
| VS Code | 1.85+ |
| Extensão Continue | Última estável |
| Ollama | 0.3+ |
| RAM | 32 GB recomendado |
| ReqSys backend | `uvicorn` em `:8000` |

## Início rápido (3 passos)

### 1. Subir Ollama e modelos

```bash
docker compose -f infra/codex-local/docker-compose.ollama.yml up -d
ollama pull qwen2.5-coder:7b
ollama pull deepseek-coder:6.7b
```

### 2. Subir ReqSys (backend + frontend)

```bash
bash scripts/iniciar_codex_local.sh
```

Acesse `http://127.0.0.1:5173/`, faça login demo e abra `/codex`.

### 3. Configurar VS Code + Continue

1. Instale a extensão **Continue** no VS Code.
2. Copie a config:

```bash
mkdir -p ~/.continue
cp infra/codex-local/continue/config.yaml ~/.continue/config.yaml
```

3. Abra o repositório ReqSys no VS Code.
4. Use `Ctrl+L` (chat) ou `Ctrl+I` (edit inline) com o modelo **Qwen2.5 Coder**.

## Modos de uso

| Modo | Onde | Quando usar |
| --- | --- | --- |
| VS Code + Continue + Ollama | Editor local | Codificação diária gratuita |
| Tela `/codex` no ReqSys | SPA Vue | Análise governada com JWT e auditoria |
| Codex Online (GitHub Pages) | Browser estático | Demo online ou endpoint remoto |

## Endpoints backend

| Método | Rota | Auth |
| --- | --- | --- |
| `POST` | `/v1/codex/analyze` | JWT |
| `GET` | `/v1/codex/status` | JWT |
| `GET` | `/v1/codex/operational-summary` | JWT |

## Variáveis de ambiente

Copie `infra/codex-local/modelos-recomendados.env.example` e ajuste:

```bash
export CODEX_OLLAMA_BASE_URL=http://localhost:11434
export CODEX_OLLAMA_MODEL=qwen2.5-coder:7b
```

## Validação

```bash
python3 tools/codex-local-online/validate.py
cd backend && . .venv/bin/activate && python -m pytest tests/test_codex_governado*.py -v --tb=short
```

## Falhas comuns

| Sintoma | Causa | Ação |
| --- | --- | --- |
| Continue sem modelo | Ollama parado | `docker compose ... up -d` |
| 401 no /codex | Sessão expirada | Refazer login no ReqSys |
| Model requires more memory | Contexto alto | Reduzir `contextLength` na config Continue |
| Provider ollama 503 | Modelo não baixado | `ollama pull qwen2.5-coder:7b` |

## Critério de pronto

- Ollama responde em `http://localhost:11434`.
- Continue usa Qwen2.5 Coder no VS Code.
- Tela `/codex` executa análise mock com `correlation_id`.
- Workflow `codex-local-online.yml` verde.

## Referências

- ADR-022: Codex Local Online
- ADR-023: Backend governado
- `docs/codex-local/DECISAO_MODELOS_CODIFICACAO.md`
