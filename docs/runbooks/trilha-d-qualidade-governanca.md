# Trilha D — Qualidade e Governança (padrão ouro)

**Data:** 2026-06-27  
**Escopo:** gate canônico padrão ouro para testes, cobertura, mutation probe, contract tests, schema validation e CI watch.

## Status

| Campo | Valor |
|---|---|
| Trilha | D |
| Padrão ouro | Sim |
| Paralelizável | Sim (matrix 6 jobs) |
| Modo | `gold_standard` |
| Substitui CI obrigatório | Não — complementa e consolida |

## Objetivo

Consolidar seis dimensões de qualidade em jobs independentes (matrix CI), permitindo paralelização massiva. A Trilha D é o **padrão ouro** de qualidade e governança para PRs, agentes e coordenador operacional.

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

## Integração padrão ouro

| Consumidor | Papel |
|---|---|
| **PR Evidence Gate** | Workflow obrigatório no head SHA |
| **PR CI Watch** | Reexecuta após conclusão da Trilha D |
| **Operational Governance Orchestrator** | Workflow crítico monitorado |
| **Coordenador Principal** | Evidência de qualidade paralelizável |
| **Runtime Health Center** | Artifact ingerido quando disponível |

## Comandos locais

```bash
# Uma dimensão (espelha job da matrix)
python scripts/trilha_d_qualidade_governanca.py --dimension coverage

# Todas as dimensões + consolidação
python scripts/trilha_d_qualidade_governanca.py --output-dir artifacts/trilha-d-qualidade-governanca

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

- Não substitui o CI ReqSys v2 Enterprise — é gate padrão ouro complementar.
- Não faz merge, deploy ou alteração de produção.
- Mutation testing usa probe leve (não mutmut completo) para manter tempo de execução baixo.
- CI watch valida estrutura local; diagnóstico de PR continua no workflow **PR CI Watch**.

## Relação com outros gates

| Gate canônico | Papel da Trilha D |
|---|---|
| CI — ReqSys v2 Enterprise | Build, lint e E2E obrigatórios |
| PR Evidence Gate | Exige Trilha D verde no head SHA |
| PR CI Watch | Diagnóstico por PR/SHA |
| Operational Artifact Schema Validation | Contratos de artifacts operacionais |
| Schema Governance Gate | Governança transversal de schemas |

## Critério de pronto (padrão ouro)

1. Workflow publica artifact `trilha-d-qualidade-governanca-evidence`.
2. JSON consolidado com `gold_standard: true`, `parallelizable: true` e seis dimensões.
3. PR Evidence Gate lista Trilha D como workflow obrigatório.
4. Testes unitários em `tests/test_trilha_d_qualidade_governanca.py` verdes.

## Referências

- `docs/REQSYS_PADRAO_OURO_TRANSVERSAL.md`
- `docs/governanca/PADRAO_OURO_ENTERPRISE.md`
- `docs/ai-governance/06-DEVOPS/QUALITY_GATES.md`
- `docs/runbooks/coordenador-principal-menu-operacional.md`
