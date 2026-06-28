# Operational CI Intelligence

Atualizado em UTC: `2026-06-28T00:08:29.791419+00:00`

## Semáforo operacional

**Status:** VERMELHO
**Score operacional:** 0%
**Runs analisados:** 3
**Matches:** 5
**Taxa de instabilidade:** 66.67%

## Pareto de falhas

| Causa | Categoria | Tier | Ocorrências | Impacto | Acumulado |
|---|---|---|---:|---:|---:|
| Regressao funcional ou teste desatualizado. | test_failure | A | 1 | 80 | 25.81% |
| Automated test failure | test_failure | A | 1 | 80 | 51.61% |
| Workflow dependente de artifact que ainda nao foi publicado ou foi nomeado fora do padrao esperado. | artifact | A | 1 | 50 | 67.74% |
| Missing or unavailable artifact | artifact | B | 1 | 50 | 83.87% |
| Python lint or formatting failure | quality_gate | C | 1 | 50 | 100.0% |

## Histórico de instabilidade

- Direção: `piorando`
- Delta instabilidade: `24.67%`
- Pontos históricos: `4`
- Média instabilidade: `50.84%`

## Distribuição

| Dimensão | Dados |
|---|---|
| Categorias | `{"artifact": 2, "quality_gate": 1, "test_failure": 2}` |
| Severidades | `{"medium": 3, "high": 2}` |
| Owners | `{"ci_cd": 4, "backend": 1}` |
| Fontes de classificação | `{"knowledge_base": 2, "failure_pattern_engine": 3}` |

## Anti-rerun infinito

- Bloqueado: `False`
- Limite: `2` reruns sem mudança de commit

## Runs classificados

| Run | Workflow | Conclusão | Risco | Owner | Rerun seguro |
|---|---|---|---:|---|---|
| 101 | CI — ReqSys v2 Enterprise | failure | 100 | ci_cd | False |
| 102 | Backend Tests + Coverage (pytest) | failure | 100 | backend | False |
| 103 | CI — ReqSys v2 Enterprise | success | 0 | ci_cd | False |

## Próximas ações recomendadas

- Congelar novos incrementos grandes ate estabilizar CI operacional.
- Priorizar Pareto tier A: Regressao funcional ou teste desatualizado. (test_failure) — 1 ocorrência(s), impacto 80.
- Corrigir regressao de teste antes de qualquer rerun adicional.
- Validar nomenclatura, retention e ordem de publicacao dos artifacts.

## Ações bloqueadas

- `auto_merge`
- `auto_fix_in_production`
- `unrestricted_rerun`
- `continue_on_error_to_hide_failure`
