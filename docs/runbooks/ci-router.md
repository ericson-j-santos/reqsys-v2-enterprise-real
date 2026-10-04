# Runbook — CI Router ReqSys

## Objetivo

Reduzir o tempo de espera dos PRs executando somente os jobs necessários conforme os arquivos alterados.

## Como funciona

O job `CI Router (paths + Pareto)` detecta os arquivos alterados e define os outputs:

| Output | Quando fica `true` |
|---|---|
| `backend` | arquivos em `backend/**` |
| `frontend` | arquivos em `frontend/**` |
| `docs` | arquivos em `docs/**`, `README.md`, `CHANGELOG.md` ou `*.md` |
| `codex_static` | arquivos em `tools/codex-local-online/**` |
| `workflows` | arquivos em `.github/workflows/**` |
| `full_ci` | arquivos não classificados ou alteração de workflows |

## Interpretação do resultado

| Cenário | Resultado esperado |
|---|---|
| Só documentação | apenas router + resultado consolidado |
| Backend | backend lint + backend tests |
| Frontend | frontend build + E2E responsivo |
| Workflow | CI completo |
| Arquivo desconhecido | CI completo |

## Comandos úteis

Listar último run:

```bash
gh run list --workflow=ci.yml --limit 5
```

Acompanhar execução:

```bash
gh run watch
```

Abrir no navegador:

```bash
gh run view --web
```

## Decisão de merge

Pode seguir para review/merge quando:

1. `CI Router Result` estiver verde;
2. jobs aplicáveis estiverem verdes;
3. jobs ignorados forem coerentes com os arquivos alterados;
4. não houver alteração transversal sem CI completo.

## Regra de exceção

Quando houver dúvida sobre impacto indireto, force CI completo alterando explicitamente uma pequena linha controlada no workflow ou executando manualmente o workflow completo.
