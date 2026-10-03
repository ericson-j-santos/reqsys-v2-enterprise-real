# Monitoramento operacional pós-merge (baseline 24h)

Runbook para validar estabilidade após merges operacionais (#618, #624) sem reintroduzir cascata `workflow_run`.

## Sinais canônicos (verificar diariamente)

| Workflow | Gate esperado | Evidência |
| --- | --- | --- |
| Main Operational Validation Fast | `success`, script &lt;100ms | `artifacts/main-operational-validation-fast/` |
| Main Operational Health | `success` (schedule 09:17 UTC dias úteis) | `artifacts/main-operational-health/` |
| Main Smoke CI | `success` em push `main` | `main-smoke-ci-evidence` |
| Fly Enterprise Sync | `success` | smoke login demo |
| Deploy ReqSys Public Showcase | `success` | GitHub Pages |

## Baseline registrada (2026-06-30)

- **Main Operational Health**: verde após fix grep acentuação (#614); último run `success` no merge #618.
- **Main Operational Validation Fast**: verde após #624 (`mkdir -p` antes do `tee`); ~5s wall-clock, `overall_state=green`.
- **Mesh hub**: últimos `workflow_run` cancelados datam de antes do #618; pós-merge dispara via schedule/dispatch apenas.
- **GitHub Pages showcase**: verde em 2026-06-30 (`deploy-reqsys-showcase-pages`).

## Comandos de verificação local

```bash
# Validação rápida da malha P0 (modo lite)
python scripts/main_operational_validation_fast.py --lite \
  --output-dir artifacts/main-operational-validation-fast

# Listar runs cancelados recentes (ruído mesh)
gh run list --workflow operational-runtime-mesh-hub.yml --limit 20 \
  --json conclusion,event,createdAt \
  --jq '[.[] | select(.conclusion=="cancelled")] | length'
```

## Critérios de alerta

1. **Main Operational Health** falha 2 dias consecutivos → investigar guardrails em `main-operational-health.yml`.
2. **&gt;5 runs `cancelled`** na mesh em 1h após merge → revisar workflows com `workflow_run` residual.
3. **Validation Fast** &gt;30s wall-clock → revisar sparse checkout ou upload de artifacts.

## Rollback

Reativar `workflow_run` apenas com decisão documentada em `config/operational-gaps-registry.json` (`OPS-GAP-MESH-NOISE`).
