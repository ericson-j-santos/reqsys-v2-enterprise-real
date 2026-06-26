# Runtime Operacional Autônomo Governado

## Objetivo

Consolidar validação de PRs, autocorreção segura de CI recorrente, evidências, analytics operacional, health checks declarados, rastreabilidade, gates, status executivo, backlog automático, maturidade, regressão, rollback governado e sincronização Fly.io em um incremento auditável.

## Entrada operacional

| Componente | Arquivo |
|---|---|
| Workflow orquestrador | `.github/workflows/runtime-health-validator.yml` |
| Runtime validator | `scripts/runtime_health_validator.py` |
| Artifact | `runtime-health-validator-evidence` |
| JSON canônico | `artifacts/runtime-health-validator/runtime-health-validator.json` |
| Dashboard navegável | `artifacts/runtime-health-validator/summary.md` |

## Camadas consolidadas

| Camada | Saída no JSON | Regra |
|---|---|---|
| Status executivo | `executive_status` | Verde, amarelo ou vermelho conforme runs recentes. |
| Maturidade operacional | `maturity` | `managed`, `defined` ou `reactive`. |
| Backlog automático | `automatic_backlog` | Gera itens `OPS-AUTO-*`, `OPS-GAP-*` e `OPS-PENDING-*`. |
| Regressão | `regression_detection` | Marca suspeita quando há workflow vermelho. |
| Rollback governado | `rollback_policy` | Ações destrutivas sempre bloqueadas automaticamente. |
| Sync Fly.io | `environment_sync` | Declara endpoints dev, homolog e prod e evidências exigidas. |
| Evidências | `evidence_consolidation` | Define artifact, arquivos e entrypoint navegável. |

## Modos de execução

```bash
python scripts/runtime_health_validator.py \
  --repo "OWNER/REPO" \
  --branch main \
  --limit 50 \
  --mode report_only \
  --output-dir artifacts/runtime-health-validator
```

| Modo | Comportamento |
|---|---|
| `report_only` | Somente consolida evidências. |
| `dry_run` | Calcula plano sem executar remediação. |
| `execute` | Executa apenas rerun allowlisted via GitHub API. |

## Gates e segurança

- Não faz merge.
- Não altera branch protection.
- Não altera secrets.
- Não executa deploy.
- Não executa rollback real.
- Não promove produção.
- Publica evidência em artifact para inspeção e auditoria.

## Critério de prontidão

O runtime é considerado pronto para revisão humana quando:

1. `state` não é `red`;
2. não existem itens `OPS-GAP-*` críticos;
3. o CI do PR está verde;
4. o artifact `runtime-health-validator-evidence` está publicado;
5. o PR permanece draft até o CI ficar verde.
