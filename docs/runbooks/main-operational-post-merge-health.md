# Main Operational Post-Merge Health

## Objetivo

Validar periodicamente a saúde operacional da branch `main` após merges, cobrindo workflows obrigatórios e workflows observados de analytics operacional.

## Workflows obrigatórios monitorados

- `CI — ReqSys v2 Enterprise`
- `Governance Quality Gates`
- `Governança Padrão Ouro`

## Workflows observados

- `CI Lead Time Analytics`
- `Operational History Snapshot`
- `Runtime Predictive Analytics`
- `Main Post-Merge Validation`

## Artifacts publicados

- `main-operational-post-merge-health.json`
- `main-operational-post-merge-health.md`

## Política operacional

- Modo `report-only`.
- Não relaxa gates obrigatórios.
- Não altera deploy/runtime.
- Não usa secrets adicionais.
- Usa somente permissões `actions: read` e `contents: read`.

## Interpretação executiva

| Indicador | Meta |
|---|---:|
| Required green percent | 100% |
| Observed green percent | >= 75% |
| Warnings críticos | 0 |

## Limites

A ausência de workflow observado no recorte recente pode indicar apenas falta de execução recente, não falha funcional. O item deve ser tratado como warning até haver evidência de falha.
