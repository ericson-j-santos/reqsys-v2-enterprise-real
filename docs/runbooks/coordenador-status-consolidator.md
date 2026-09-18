# Coordenador Status Consolidator

## Objetivo

Gerar um unico artifact executivo (`coordenador-status.json`) a partir dos artifacts 1 e 2 do menu operacional:

- Operational Governance Orchestrator
- Runtime Health Validator

## Escopo

O consolidator:

- consulta GitHub Actions (ou aceita JSONs locais);
- gera os dois relatorios-fonte em `sources/`;
- calcula semaforo global, decisao e acoes recomendadas;
- publica artifact `coordenador-status-evidence`.

## Fora de escopo

- Merge, deploy ou alteracao de producao
- Disparo automatico de remediacao
- Substituir leitura de PR CI Watch por PR

## Arquivos

| Arquivo | Funcao |
|---|---|
| `.github/workflows/coordenador-status-consolidator.yml` | Workflow agendado e manual |
| `scripts/coordenador_status_consolidator.py` | Consolidacao report-only |
| `tests/test_coordenador_status_consolidator.py` | Testes unitarios |
| `docs/runbooks/coordenador-principal-menu-operacional.md` | Menu operacional do coordenador |

## Gatilhos

| Evento | Comportamento |
|---|---|
| `schedule` (`13 * * * *`) | Consolidacao horaria (6 min apos orchestrator) |
| `workflow_dispatch` | Consolidacao manual com `branch` opcional |

## Artifact

Nome: `coordenador-status-evidence`

| Arquivo | Uso |
|---|---|
| `coordenador-status.json` | **Leitura unica do coordenador** — `state`, `decision`, `increment_gate`, `recommended_actions` |
| `summary.md` | Resumo navegavel |
| `sources/operational-governance-orchestrator/operational-governance-orchestrator.json` | Fonte 1 |
| `sources/runtime-health-validator/runtime-health-validator.json` | Fonte 2 |
| `sources/repository-health-watchdog/repository-health-report.json` | Fonte 3 (PRs duplicados) |

## Decisao operacional

| `state` | Significado | Acao |
|---|---|---|
| `green` | Fontes verdes | Continuar proximo incremento |
| `yellow` | Pendencias ou ausencias | Validar logs antes de merge |
| `red` | Falha real ou gap critico | Bloquear merges; tratar gaps |

## Execucao local (com JSONs de fixture)

```bash
cd /workspace
python scripts/coordenador_status_consolidator.py \
  --orchestrator-json path/to/operational-governance-orchestrator.json \
  --health-json path/to/runtime-health-validator.json \
  --output-dir artifacts/coordenador-status
```

## Guardrails

| Guard rail | Valor |
|---|---|
| `merge` | false |
| `deploy` | false |
| `production_change` | false |
| `rerun` | false |

## Links

- Menu operacional: [coordenador-principal-menu-operacional.md](coordenador-principal-menu-operacional.md)
- Orchestrator: [operational-governance-orchestrator.md](operational-governance-orchestrator.md)
- Health validator: [runtime-health-validator.md](runtime-health-validator.md)
