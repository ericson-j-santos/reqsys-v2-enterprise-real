# Coordenador Status Consolidado

- Correlation ID: `d61aa286-015e-451d-ad3d-c54278c2103e`
- Repository: ``
- Branch: `main`
- State: `yellow`
- Decision: `bloquear_novas_frentes_ate_consolidar`
- Executive status: `Operacao requer acompanhamento — validar pendencias antes de promover`
- Operational score: `None%`
- Runtime score: `65`
- Maturity: `managed`
- Quarantine active: `False`
- New front allowed: `False`
- Generated at: `2026-06-28T00:08:30Z`

## Increment gate

- Policy: Nao abrir frentes novas sem incremento objetivo. Ciclo: triagem -> ajuste minimo -> CI -> evidencia -> merge.
- Blockers: `state_yellow`
- Allowed types: `gap_fix, hotfix, consolidate`

## Summary

| Metric | Value |
|---|---:|
| `open_prs` | `2` |
| `draft_prs` | `0` |
| `backlog_items` | `0` |
| `critical_gaps` | `0` |
| `red_workflows` | `0` |
| `pending_workflows` | `0` |
| `missing_critical_workflows` | `0` |
| `regression_state` | `no_regression_detected` |
| `duplicate_pr_groups` | `0` |
| `new_front_allowed` | `False` |

## Recommended actions

- `P1` · `bloquear_nova_frente` · `state_yellow` — Resolver bloqueios antes de abrir branch/PR novo

## Sources

- `orchestrator`: state=`yellow`
- `runtime_health`: state=`green`
- `watchdog`: available=`False` duplicates=`[]`

## Guardrails

- `merge`: `False`
- `deploy`: `False`
- `production_change`: `False`
- `branch_protection_change`: `False`
- `rerun`: `False`
- `new_front`: `True`
