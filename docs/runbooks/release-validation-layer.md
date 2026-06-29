# Release Validation Layer — ReqSys

## Objetivo

Consolidar evidencias de release em um unico estado operacional com quality gates centralizados, validacao semantica de CI e release readiness score. Reduz falsos verdes, PRs inconsistentes e validacao manual fragmentada.

## Quando usar

- Antes de promover ambiente (dev → hml → prod).
- Apos merges na `main` para validar prontidao da rodada.
- No menu do Coordenador Principal como fonte de release readiness.
- Em revisao executiva de release (dashboard consolidado).

## Componentes

| Componente | Caminho / artifact |
|---|---|
| Script agregador | `scripts/release_validation_layer.py` |
| Workflow | `.github/workflows/release-validation-layer.yml` |
| Artifact CI | `release-validation-layer-evidence` |
| JSON consolidado | `audit/release-validation/release-validation-layer.json` |
| Dashboard executivo | `audit/release-validation/executive-release-dashboard.json` |
| Schema | `docs/contracts/release-validation-layer.schema.json` |

## Fontes consolidadas

1. `coordenador-status-evidence` — estado operacional e increment gate.
2. `pr-evidence-gate.json` — CI obrigatorio no head SHA dos PRs.
3. `golden-release-readiness.json` — checklist operacional versionado.
4. `main-post-merge-validation.json` — saude pos-merge da main.
5. OpenAPI routes drift + semantic diff — validacao semantica de contratos.

## Quality gates centralizados

| Gate | Descricao |
|---|---|
| `coordenador_operational_state` | Estado global do coordenador (green/yellow/red) |
| `pr_evidence_gate` | Workflows obrigatorios verdes no PR |
| `golden_release_readiness` | Checklist golden release |
| `main_post_merge_validation` | Validacao pos-merge |
| `ci_semantic_validation` | Drift OpenAPI canonico + semantico |

## Release readiness score

Media ponderada dos gates com fonte disponivel:

- **≥ 95%** → `ready`
- **≥ 85%** → `ready_with_observation`
- **≥ 70%** → `needs_review`
- **Blockers ativos** → `blocked` (independente do score)

## Execucao local

```bash
python3 scripts/release_validation_layer.py \
  --repo owner/repo \
  --branch main \
  --output-dir audit/release-validation
```

Com artifacts locais ja presentes em `artifacts/coordenador-status/` e `audit/`.

## Schedule CI

```text
:07 orchestrator → :13 coordenador → :17 release validation → :23 runtime health
```

## Modo

`report_only` — nao faz deploy, nao relaxa gates obrigatorios, nao muta producao. Requer revisao humana antes de promover.

## Integracao coordenador

O `coordenador-status-consolidator` consome `release-validation-layer.json` quando disponivel e expoe `sources.release_validation` + `summary.release_readiness_score`.

## Rollback

Desabilitar workflow `Release Validation Layer` ou remover consumo no coordenador. Nao afeta CI obrigatorio nem branch protection.
