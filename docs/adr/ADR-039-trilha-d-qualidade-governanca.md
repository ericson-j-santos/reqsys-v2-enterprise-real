# ADR-039 — Trilha D: Qualidade e Governança

## Status

Aceito em 2026-06-27.

## Contexto

A Trilha D já orquestrava seis dimensões paralelizáveis de qualidade (tests, coverage, mutation, contract, schema, ci-watch), mas faltava ADR formal e manifest architecture-as-code para fechar o pacote padrão ouro.

## Decisão

Formalizar governança completa da **Trilha D — Qualidade e Governança**:

| Dimensão | Validação |
|---|---|
| `tests` | pytest backend completo |
| `coverage` | gate `--cov-fail-under=60` |
| `mutation` | probe leve em rotas críticas |
| `contract` | testes `*contract*` + artifact validator |
| `schema` | schemas JSON + registry |
| `ci-watch` | estrutura PR CI Watch |

Workflow matrix + job consolidate publica `trilha-d-qualidade-governanca-evidence`.

## Regras de governança

| Tema | Decisão |
|---|---|
| Modo | `report_only` por padrão; `fail_on_error` apenas em dispatch explícito |
| CI canônico | Não substitui **CI — ReqSys v2 Enterprise** |
| Paralelização | `fail-fast: false` na matrix |
| Mutation | Probe leve, não mutmut completo |

## Consequências

### Benefícios

- Visão consolidada de qualidade para agentes e coordenador.
- Paralelização massiva sem duplicar lógica do CI principal.

### Limitações

- Artifact local pode falhar sem venv/pytest; CI é fonte de verdade.
- Schema governance pode emitir warnings sem bloquear dimensão schema.

## Referências

- `docs/runbooks/trilha-d-qualidade-governanca.md`
- `scripts/trilha_d_qualidade_governanca.py`
- `tests/test_trilha_d_qualidade_governanca.py`
