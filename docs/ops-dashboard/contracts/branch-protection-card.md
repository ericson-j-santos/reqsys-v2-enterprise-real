# BranchProtectionMaturityCard — Contrato de Integração

## Objetivo

Definir o contrato seguro para conectar a maturidade de Branch Protection ao dashboard operacional sem conflitar com PRs de runtime/dashboard em andamento.

## Fonte canônica

```text
docs/ops-dashboard/data/branch-protection-maturity.json
```

## Campos obrigatórios

| Campo | Uso visual |
|---|---|
| `maturity_percent` | KPI principal do card |
| `operational_risk` | Semáforo de risco |
| `confidence_level` | Indicador de confiança da evidência |
| `safe_parallel_pr_capacity.current_recommended_range` | Capacidade segura atual de PRs paralelos |
| `safe_parallel_pr_capacity.aggressive_governed_range` | Capacidade agressiva governada |
| `missing_evidence` | Alertas e próximos passos |
| `evidence` | Drill-down para artefatos e baseline |

## Regra de semáforo

| Condição | Status visual |
|---|---|
| `maturity_percent >= 90` e sem evidência faltante | Verde |
| `maturity_percent >= 70` com evidência faltante | Amarelo |
| `maturity_percent < 70` | Vermelho |

## Restrições

- Não alterar rulesets ou branch protection pela UI.
- Não disparar merge/deploy pelo card.
- Não duplicar `health.json` como agregador paralelo.
- Não bloquear PRs automaticamente sem evidência atualizada de ruleset.

## Critérios de aceite

- Card exibe maturidade, risco, confiança e capacidade segura de PRs.
- Evidência faltante aparece como warning.
- Drill-down aponta para baseline, artifact e lacunas.
- Integração futura pode ser feita sem alterar contrato dos dados já mergeados.
