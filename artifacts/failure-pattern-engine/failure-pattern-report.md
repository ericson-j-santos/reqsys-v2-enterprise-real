# Failure Pattern Engine — Relatorio

Atualizado em UTC: `2026-06-28T00:08:29.826945+00:00`

## Semaforo

**Status:** VERMELHO
**Score de risco:** 100%
**Leitura:** Foram identificadas falhas conhecidas de alta severidade. Priorizar estabilizacao antes de prosseguir.

## Escopo analisado

- `/workspace/artifacts/failure-pattern-engine/input-sample.log`

## Estatisticas

| Indicador | Valor |
|---|---:|
| Matches | 2 |
| Categorias | 2 |
| Severidades | 2 |

## Matches encontrados

| ID | Severidade | Categoria | Arquivo | Acao recomendada |
|---|---|---|---|---|
| FPE-GH-PERM-001 | high | permissions | `/workspace/artifacts/failure-pattern-engine/input-sample.log` | Validar permissions do workflow, escopo do GITHUB_TOKEN e uso de pull_request_target apenas quando houver justificativa e guardrails. |
| FPE-GH-ARTIFACT-001 | medium | artifact | `/workspace/artifacts/failure-pattern-engine/input-sample.log` | Validar etapa de upload, nome do artifact, retention-days e permissao de leitura do workflow. |

## Limites operacionais

- Classificacao baseada em padroes deterministos e texto disponivel.
- Nao executa rerun, merge, push, deploy ou remediacao automatica.
- Resultado sem matches nao garante ausencia de falha desconhecida.
