# Runbook — Operational Actions Center

## Objetivo

Capturar e classificar execuções do GitHub Actions sem depender de envio manual de links de run.

## Endpoints

| Método | Endpoint | Perfil | Finalidade |
|---|---|---|---|
| GET | `/v1/actions-runtime/status` | autenticado | validar disponibilidade |
| POST | `/v1/actions-runtime/snapshot` | autenticado | classificar runs enviados manualmente |
| GET | `/v1/actions-runtime/github/runs` | admin | consultar GitHub Actions API |
| POST | `/v1/actions-runtime/webhook/github` | admin | receber evento `workflow_run` |

## Variáveis

| Variável | Uso |
|---|---|
| `REQSYS_GITHUB_TOKEN` | token para consultar GitHub Actions API |
| `GITHUB_TOKEN` | alternativa para execução em ambiente GitHub |

## Exemplo de consulta

```bash
curl -H "Authorization: Bearer <jwt_admin>" \
  "http://localhost:8000/v1/actions-runtime/github/runs?repo=ericson-j-santos/reqsys-v2-enterprise-real&branch=main&per_page=20"
```

## Interpretação

| Health | Significado | Decisão |
|---|---|---|
| `healthy` | run concluído com sucesso | seguir |
| `running` | run em andamento | aguardar |
| `unhealthy` | falha, cancelamento ou timeout | corrigir antes de merge |
| `unknown` | estado não mapeado | investigar |

## Decisão operacional

O campo `decisao` deve orientar a próxima ação:

- `operacao_estavel`
- `aguardar_finalizacao_dos_workflows`
- `corrigir_falhas_de_actions_antes_de_novo_merge`
- `investigar_instabilidade_operacional`

## Próximo incremento

Persistir snapshots em banco e expor visualização no Runtime Center.
