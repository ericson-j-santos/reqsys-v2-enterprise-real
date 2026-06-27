# Trilha D — Qualidade e Governança

**Data:** 2026-06-27  
**Escopo:** orquestração paralelizável de testes, cobertura, mutation probe, contract tests, schema validation e CI watch.

## Objetivo

Consolidar seis dimensões de qualidade em jobs independentes (matrix CI), permitindo paralelização massiva sem duplicar a lógica do CI principal.

| Dimensão | O que valida | Job matrix |
|---|---|---|
| `tests` | `pytest` backend completo | `trilha-d-matrix` |
| `coverage` | Cobertura com gate `--cov-fail-under=60` | `trilha-d-matrix` |
| `mutation` | Mutation probe leve em rotas críticas | `trilha-d-matrix` |
| `contract` | Testes `*contract*` + artifact validator | `trilha-d-matrix` |
| `schema` | Schemas JSON em `docs/contracts/` + registry | `trilha-d-matrix` |
| `ci-watch` | Estrutura local do PR CI Watch | `trilha-d-matrix` |

## Workflow

- Arquivo: `.github/workflows/trilha-d-qualidade-governanca.yml`
- Script: `scripts/trilha_d_qualidade_governanca.py`
- Artifact consolidado: `trilha-d-qualidade-governanca-evidence`
- JSON canônico: `artifacts/trilha-d-qualidade-governanca/trilha-d-qualidade-governanca.json`

## Comandos locais

```bash
# Todas as dimensões (sequencial local)
python scripts/trilha_d_qualidade_governanca.py --output-dir artifacts/trilha-d-qualidade-governanca

# Uma dimensão (espelha job da matrix)
python scripts/trilha_d_qualidade_governanca.py --dimension coverage

# Consolidar após artifacts por dimensão
python scripts/trilha_d_qualidade_governanca.py --consolidate --output-dir artifacts/trilha-d-qualidade-governanca
```

## Paralelização

O workflow usa `strategy.matrix` com `fail-fast: false` para executar as seis dimensões em paralelo. O job `trilha-d-consolidate` agrega os JSONs e publica o relatório executivo.

## Semáforo

| Estado | Condição | Decisão |
|---|---|---|
| `passed` | Nenhuma dimensão falhou | `continuar_incremento_qualidade` |
| `warning` | Warnings sem falha dura | `validar_warnings_antes_de_merge` |
| `failed` | Qualquer dimensão falhou | `bloquear_merge_ate_corrigir_qualidade` |

## Guardrails

- Modo padrão: `report_only` (não substitui CI obrigatório ReqSys v2 Enterprise).
- Não faz merge, deploy ou alteração de produção.
- Mutation testing usa probe leve (não mutmut completo) para manter tempo de execução baixo.
- CI watch valida estrutura local; diagnóstico de PR continua no workflow **PR CI Watch**.

## Relação com outros gates

| Gate canônico | Papel da Trilha D |
|---|---|
| CI — ReqSys v2 Enterprise | Gate obrigatório de merge |
| PR CI Watch | Diagnóstico por PR/SHA |
| Operational Artifact Schema Validation | Contratos de artifacts operacionais |
| Schema Governance Gate | Governança transversal de schemas |

A Trilha D complementa esses gates com visão consolidada paralelizável para agentes e coordenador operacional.

## Critério de pronto

1. Workflow publica artifact `trilha-d-qualidade-governanca-evidence`.
2. JSON consolidado com `parallelizable: true` e seis dimensões.
3. Testes unitários em `tests/test_trilha_d_qualidade_governanca.py` verdes.
