# ReqSys Operational Intelligence Hub

Atualizado em UTC: `2026-06-28T00:08:29.855552+00:00`

## Semáforo consolidado

**Status:** VERMELHO
**Score:** 0.0%
**Confiança:** media

## Camadas

| Camada | Disponível | Status | Score | Fonte |
|---|---:|---|---:|---|
| operational_health | False | - | - | `artifacts/operational-health/operational-health.json` |
| operational_ci_intelligence | True | VERMELHO | - | `artifacts/operational-ci-intelligence/operational-ci-intelligence.json` |
| failure_pattern_engine | True | VERMELHO | 100 | `artifacts/failure-pattern-engine/failure-pattern-report.json` |
| actions_deep_diagnostic | False | - | - | `artifacts/deep-diagnostic/deep-diagnostic.json` |

## Componentes do score

| Componente | Score | Peso |
|---|---:|---:|
| operational_ci_intelligence | 0.0 | 0.35 |
| failure_pattern_engine | 0 | 0.2 |

## Recomendações

- Congelar novos incrementos grandes ate estabilizar CI operacional.
- Priorizar Pareto tier A: Regressao funcional ou teste desatualizado. (test_failure) — 1 ocorrência(s), impacto 80.
- Corrigir regressao de teste antes de qualquer rerun adicional.
- Validar nomenclatura, retention e ordem de publicacao dos artifacts.

## Ações bloqueadas

- `auto_merge`
- `auto_fix_in_production`
- `unrestricted_rerun`
- `bypass_ci`
- `hide_failure_with_continue_on_error`

## Limites

- Relatorio consolidado depende dos artifacts/arquivos de entrada disponiveis.
- Ausencia de evidencia em uma camada nao significa ausencia de problema.
- Nenhuma remediacao, rerun, merge ou deploy e executado por este hub.
