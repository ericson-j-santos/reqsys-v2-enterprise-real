# Runtime Validation Consolidator

## Objetivo

Consolidar em um único snapshot auditável:

- smoke checks públicos (`public-runtime-validation`);
- readiness operacional (`ops-readiness-report`);
- validação pós-merge (`main-post-merge-validation`);
- health validator e health center;
- trilha A e evidence gate.

Eleva o **Padrão Ouro de risco operacional** para cobertura contínua sem alterar contratos nem secrets.

## Modo de operação

- **report_only** — nunca faz merge, deploy ou captura segredos.
- Distingue evidência **strict** vs **scheduled** do Public Runtime Evidence Gate.
- Publica artifact `runtime-validation-evidence`.

## Comandos locais

```bash
python3 scripts/runtime_validation_consolidator.py \
  --repo "${GITHUB_REPOSITORY:-local/reqsys}" \
  --branch main \
  --output-dir artifacts/runtime-validation-consolidator \
  --publish-executive-brief docs/ops-dashboard/data/executive-brief.json
```

## Workflow

- `.github/workflows/runtime-validation-consolidator.yml`
- Disparo: `workflow_dispatch`, schedule horário, `workflow_run` após gates de runtime/pós-merge.

## Artifacts

| Arquivo | Uso |
|---|---|
| `runtime-validation-snapshot.json` | Contrato machine-readable |
| `summary.md` | Leitura humana / menu operacional |
| `executive-brief.json` | Indicadores executivos e semáforo |
| `operational-acceptance-record.json` | Aceite operacional automático (Padrão Ouro) |

## Aceite operacional (Padrão Ouro)

Quando `production_ready=true`, o consolidator grava automaticamente:

- `audit/operational-acceptance/operational-acceptance-record.json`
- `operational_acceptance` no `executive-brief.json` com `status: accepted`

Critérios (`compute_production_ready`):

- `gold_standard_operational_risk.status` = `gold`
- `public_runtime_ready` = true
- `validation_score` ≥ 90
- `operational_risk_percent` ≤ 15
- Sem bloqueadores críticos (`*_failed`, `public_runtime_not_evidenced`, risco abaixo do limiar)

`post_merge_validation_incomplete` **não** bloqueia aceite operacional — permanece como ação P1 recomendada.

## Integrações

- `coordenador_status_consolidator.py` — fonte `runtime_validation`.
- `build_runtime_executive_index.py` — card de validação consolidada.
- `post_workflow_evidence_snapshot.py` — maturity pós-CI.
- `docs/ops-dashboard/data/executive-brief.json` — brief executivo publicado.

## Gates e bloqueios

Bloqueios reportados (não enforced por branch protection neste incremento):

- `public_runtime_not_evidenced`
- `post_merge_validation_incomplete`
- `operational_risk_below_gold_threshold`
- `{domain}_failed` para domínios em vermelho

## Meta Padrão Ouro

`gold_standard_operational_risk.overall_score` = **100%** quando:

- cobertura de fontes ≥ 95%;
- domínios verdes ≥ 85%;
- validation_score ≥ 90.

## Próximas ações operacionais

1. Manter cadência horária do consolidator.
2. Encadear após Public Runtime Evidence Gate strict green.
3. Consumir `executive-brief.json` no ops dashboard.
