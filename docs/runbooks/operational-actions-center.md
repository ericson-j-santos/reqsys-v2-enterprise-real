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
| `GITHUB_TOKEN` | token para consulta GitHub Actions API |
| `REQSYS_GITHUB_TOKEN` | fallback governado para token dedicado |

## Operação

1. Validar autenticação.
2. Chamar `/v1/actions-runtime/status`.
3. Para análise manual, enviar runs para `/v1/actions-runtime/snapshot`.
4. Para consulta real, configurar token e usar `/v1/actions-runtime/github/runs`.
5. Para eventos automatizados, configurar webhook GitHub com evento `workflow_run`.

## Decisão operacional

| Decisão | Ação |
|---|---|
| `operacao_estavel` | permitir continuidade da fila |
| `aguardar_finalizacao_dos_workflows` | não promover nem mergear |
| `corrigir_falhas_de_actions_antes_de_novo_merge` | bloquear merge e abrir correção |
| `investigar_instabilidade_operacional` | avaliar ruído/flaky antes de promover |

## Segurança

- Nunca registrar token GitHub em log.
- Nunca retornar token em payload de API.
- Endpoints de consulta real e webhook exigem perfil admin.
- A automação não executa merge ou retry automaticamente no P0.
