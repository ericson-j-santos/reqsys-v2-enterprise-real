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

## Matriz de decisao executiva

| Estado | Condicao minima | Decisao recomendada | Acao obrigatoria |
|---|---|---|---|
| `ready` | Score >= 95%, sem blockers e fontes criticas presentes | Promover com aprovacao normal | Registrar evidencia e changelog |
| `ready_with_observation` | Score >= 85%, sem blockers, com observacoes nao bloqueantes | Promover somente com aceite consciente | Registrar observacoes, dono e prazo |
| `needs_review` | Score >= 70% ou fonte relevante ausente | Nao promover automaticamente | Abrir plano de correcao e nova validacao |
| `blocked` | Qualquer blocker ativo | Bloquear promocao | Corrigir blocker, reexecutar gates e anexar evidencia |

## Politica de fontes ausentes

| Fonte ausente | Severidade padrao | Tratamento |
|---|---|---|
| `pr-evidence-gate.json` | Alta | Impede promocao quando houver PR relacionado |
| `main-post-merge-validation.json` | Alta | Exige validacao pos-merge antes de release |
| `golden-release-readiness.json` | Media | Permite apenas `ready_with_observation` quando demais gates estiverem verdes |
| Evidencias OpenAPI | Alta para mudancas de contrato; media para docs-only | Exige revisao semantica quando houver API afetada |
| `coordenador-status-evidence` | Alta | Exige validacao consolidada alternativa ou nova execucao do coordenador |

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

## Limites operacionais

- Nao substitui branch protection, CI obrigatorio ou aprovacao humana.
- Nao deve transformar alerta report-only em permissao automatica de producao.
- Nao deve mascarar falta de artifact critico como estado verde.
- Nao deve ser usado como unica evidencia para mudancas de seguranca, autenticacao, banco ou contrato publico.

## Integracao coordenador

O `coordenador-status-consolidator` consome `release-validation-layer.json` quando disponivel e expoe `sources.release_validation` + `summary.release_readiness_score`.

## Integracao promotion pipeline

O `governed-promotion-pipeline.yml` consome `release-validation-layer-evidence` como pre-condicao:

| Ambiente | Score minimo | Readiness permitido | Estado operacional |
|---|---:|---|---|
| homolog | 70% | ready, ready_with_observation, needs_review | bloqueia se red |
| prod | 85% | ready, ready_with_observation | bloqueia se red ou yellow |

- `dry_run=true`: simula e registra `promotion_would_block` sem executar promocao.
- `dry_run=false`: bloqueia promocao real quando release validation falha ou artifact ausente.
- Avaliacao: `scripts/evaluate_promotion_release_gate.py` → `artifacts/governed-promotion/release-validation-gate.json`.

## Rollback

Desabilitar workflow `Release Validation Layer` ou remover consumo no coordenador. Nao afeta CI obrigatorio nem branch protection.