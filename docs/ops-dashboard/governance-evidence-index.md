# Governance Evidence Index

Atualizado em: 2026-06-27

## Objetivo

Centralizar as principais evidências de governança operacional do ReqSys em um índice navegável para leitura executiva e técnica.

## Evidências principais

| Capacidade | Workflow / Gate | Artifact esperado |
|---|---|---|
| Predição de conflito | `PR Conflict Guard` + `scripts/conflict_prediction_gate.py` | `conflict-prediction-gate-evidence` |
| Merge queue runtime-aware | `Governed Merge Queue` + `scripts/runtime_merge_queue_gate.py` | `governed-merge-queue-policy-evidence` |
| Preview environment | `Preview Environment Contract` | `preview-environment-evidence` |
| Gate de PR governado | `Governed PR Automation` | `governed-pr-increment-gate-evidence` |
| Saúde operacional | `Enterprise Runtime Governance Gates` | runtime/governance artifacts |
| Evidência de PR | `PR Evidence Gate` | PR evidence artifact |

## Fluxo operacional alvo

```text
PR aberto
  -> PR Conflict Guard
  -> Preview Environment Contract
  -> Governed Merge Queue
  -> Governed PR Automation
  -> evidência pós-merge
```

## Contratos JSON relevantes

### Conflict Prediction Gate

Arquivo esperado:

```text
artifacts/conflict-prediction/conflict-prediction-gate.json
```

Campos principais:

- `risk`
- `lane`
- `parallel_safe`
- `blocking_reasons`
- `changed_paths`
- `signals`

### Runtime Merge Queue Gate

Arquivo esperado:

```text
artifacts/governed-merge-queue/runtime-merge-queue-gate.json
```

Campos principais:

- `eligible`
- `state`
- `lane`
- `blocking_reasons`
- `evidence`

### Preview Environment Evidence

Arquivo esperado:

```text
artifacts/preview-environment/preview-environment-evidence.json
```

Campos principais:

- `mode`
- `pr`
- `environment`
- `url`
- `status`
- `checks`
- `correlation_id`
- `production_isolation`

## Estado evidenciado

| Área | Estado |
|---|---|
| Contrato de merge queue runtime-aware | Consolidado |
| Contrato de preview environment | Consolidado |
| Contrato de conflict prediction | Consolidado |
| Gate executável de merge queue | Implementado |
| Gate executável de conflict prediction | Implementado |
| Workflow preview dry-run | Implementado |
| Integração dos gates nos workflows | Em validação no PR de integração |
| Dashboard navegável de evidências | Índice inicial criado |

## Próximos incrementos recomendados

1. Criar `docs/ops-dashboard/data/governance-evidence-index.json` para consumo por UI.
2. Expor cards no dashboard operacional para cada artifact.
3. Criar links para últimas execuções relevantes de workflows.
4. Adicionar severidade visual por estado.
5. Criar histórico por PR para maturidade operacional.
