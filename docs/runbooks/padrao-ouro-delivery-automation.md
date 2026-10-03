# Padrão Ouro Delivery Automation

Automatiza **abertura de PR draft** para branches `cursor/*` e **deploy Fly.io + smoke** `/api/runtime/*` após merge/push em `main`.

## Workflow

```text
.github/workflows/padrao-ouro-delivery-automation.yml
```

## Secrets obrigatórios

| Secret | Uso |
|---|---|
| `GH_PAT_ACTIONS` | Criar/atualizar PR draft via API (escopo `repo`, Actions read/write) |
| `FLY_API_TOKEN` | Deploy automático em `reqsys-api` após merge em `main` |

Sem `GH_PAT_ACTIONS`, o job publica o artifact `auto-pr-request` com título/corpo prontos para retry manual ou consumo por automação externa.

## Configuração do repositório

Em **Settings → Actions → General**:

1. Workflow permissions: **Read and write**
2. Marcar: **Allow GitHub Actions to create and approve pull requests**

Sem isso, mesmo com PAT, o `GITHUB_TOKEN` padrão retorna `403` ao criar PR.

## Fluxo automático

```text
push cursor/*  → auto-open draft PR (+ artifact auto-pr-request)
merge main     → validate runtime → flyctl deploy → smoke /api/runtime/*
```

## Disparo manual

```bash
gh workflow run padrao-ouro-delivery-automation.yml \
  --ref cursor/padrao-ouro-ciclos-88ba \
  -f action=open_pr_only

gh workflow run padrao-ouro-delivery-automation.yml \
  --ref main \
  -f action=deploy_runtime_only
```

## Guardrails

- Deploy usa environment `production`
- Smoke falha se `/api/runtime/health|readiness|liveness` retornarem 404
- Modo report-only para artifacts; sem merge automático
