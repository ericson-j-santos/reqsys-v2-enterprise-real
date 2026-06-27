# Branch Protection Maturity — Card Operacional

## Objetivo

Expor no dashboard operacional a maturidade de Branch Protection e a capacidade segura de PRs paralelos após a consolidação da Merge Queue Governada.

## Fonte de dados

```text
docs/ops-dashboard/data/branch-protection-maturity.json
```

## Indicadores recomendados

| Indicador | Fonte | Estado atual |
|---|---|---|
| Maturidade Branch Protection | `maturity_percent` | 70% |
| Risco operacional | `operational_risk` | Médio |
| Confiança | `confidence_level` | Média |
| Capacidade segura de PRs | `safe_parallel_pr_capacity.current_recommended_range` | 4–7 |
| Capacidade agressiva governada | `safe_parallel_pr_capacity.aggressive_governed_range` | 8–12 |
| Evidência faltante | `missing_evidence` | Ruleset API snapshot |

## Critério de semáforo

| Condição | Status |
|---|---|
| `maturity_percent >= 90` e sem evidência faltante | Verde |
| `maturity_percent >= 70` com evidência faltante não crítica | Amarelo |
| `maturity_percent < 70` ou ausência de baseline | Vermelho |

## Drill-down recomendado

Ao clicar no card, abrir:

1. baseline de branch protection;
2. artifact JSON de auditoria;
3. resumo executivo;
4. evidência faltante;
5. capacidade segura de PRs paralelos por domínio.

## Próximo incremento

Conectar este arquivo ao componente visual do dashboard operacional, sem duplicar fonte de dados e preservando `docs/ops-dashboard/data/health.json` como agregador principal.
