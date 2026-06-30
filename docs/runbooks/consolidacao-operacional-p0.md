# Consolidação Operacional P0 — Malha, Evidence Gate e Analytics Cross-Runtime

Runbook para o incremento de consolidação operacional que fecha o loop entre:

```text
Operational Runtime Mesh Hub
  → Operational Alert Intelligence
    → Unified Operational Event Bus
      → Unified Operational Signal Consolidator
        → Runtime Validation Consolidator / Coordenador Principal
```

## Componentes

| Componente | Script | Artifact |
| --- | --- | --- |
| Mesh Hub | `scripts/operational_runtime_mesh_hub.py` | `artifacts/operational-runtime-mesh-hub/` |
| Alert Intelligence | `scripts/operational_alert_intelligence.py` | `artifacts/operational-alert-intelligence/` |
| Event Bus | `scripts/unified_operational_event_bus.py` | `artifacts/unified-operational-event-bus/` |
| Signal Consolidator | `scripts/unified_operational_signal_consolidator.py` | `artifacts/unified-operational-signal-consolidator/` |
| Evidence Gate consolidado | `scripts/runtime_validation_consolidator.py` | `evidence_gate_consolidated` em `runtime-validation-snapshot.json` |
| Analytics cross-runtime | `tools/product_intelligence/generate_github_runtime_analytics.py` | `reports/github-runtime-analytics/` |

## Execução local (report-only)

```bash
# 1. Mesh hub com hidratação de artifacts locais
python scripts/operational_runtime_mesh_hub.py \
  --source-workflow "manual" \
  --source-conclusion success

# 2. Alert intelligence
python scripts/operational_alert_intelligence.py \
  --workflow "Operational Runtime Mesh Hub" \
  --conclusion success

# 3. Event bus
python scripts/unified_operational_event_bus.py \
  --workflow "Operational Alert Intelligence" \
  --conclusion success

# 4. Analytics cross-runtime
python tools/product_intelligence/generate_github_runtime_analytics.py

# 5. Signal consolidator (fecha o loop)
python scripts/unified_operational_signal_consolidator.py \
  --repo "owner/repo" --branch main

# 6. Runtime validation com evidence gate consolidado
python scripts/runtime_validation_consolidator.py \
  --repo "owner/repo" --branch main

# 7. Coordenador com malha operacional
python scripts/coordenador_status_consolidator.py \
  --orchestrator-json artifacts/coordenador-status/sources/operational-governance-orchestrator/operational-governance-orchestrator.json \
  --health-json artifacts/coordenador-status/sources/runtime-health-validator/runtime-health-validator.json \
  --repo owner/repo --branch main
```

## Workflows CI

| Workflow | Papel |
| --- | --- |
| `Operational Runtime Mesh Hub` | Entrada central da malha |
| `Operational Alert Intelligence` | Classificação governada de alertas |
| `Unified Operational Event Bus` | Roteamento de eventos operacionais |
| `Unified Operational Signal Consolidator` | Contrato único consumível |
| `Runtime Validation Consolidator` | Evidence Gate consolidado |
| `Coordenador Status Consolidator` | Decisão executiva e increment gate |

## Critérios de maturidade P0

- `mesh_integrated: true` no artifact `unified-operational-signal.json`
- `evidence_gate_consolidated.consolidated: true` com pelo menos 2 camadas
- `cross_runtime_analytics.sources_hydrated >= 3`
- Coordenador expõe `sources.operational_mesh` e `summary.evidence_gate_consolidated`

## P1 — Consumo SPA (implementado)

- Endpoint: `GET /api/runtime/operational-mesh`
- Dashboard schema `1.4.0` expõe `operational_mesh`, `cross_runtime_analytics` e seção `operational-mesh-chain`
- Views: `/analytics` e `/monitoramento-operacional` (seção `malha-operacional`)
- Telemetria central: `GET /api/runtime/analytics` inclui `operational_mesh` e `cross_runtime_analytics`

## Fora de escopo (P1+ restante)

- WebSocket / realtime streaming
- Auto-remediation hooks
- Message bus persistente externo
- Novas rotas SPA

## Rollback

Reverter para workflows bash-only e remover consumo de `operational_mesh` no coordenador. Artifacts antigos permanecem compatíveis (`schema_version` incrementado, campos adicionais opcionais).
