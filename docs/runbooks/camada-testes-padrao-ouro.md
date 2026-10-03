# Camada de Testes — Padrão Ouro

**Data:** 2026-06-29  
**Escopo:** governança Tier 1 da camada de testes — pirâmide, árvores, gates, validador e evidências.

**Playbook Tier 1:** [`docs/padrao-ouro/TESTING_PLAYBOOK.md`](../padrao-ouro/TESTING_PLAYBOOK.md)

## Objetivo

Elevar a camada de testes ao mesmo nível de maturidade documental das demais frentes Padrão Ouro: playbook navegável, architecture-as-code, schema de relatório, validador report-only e integração ao Living Architecture Index.

## Componentes

| Componente | Caminho |
| --- | --- |
| Testing Playbook (Tier 1) | `docs/padrao-ouro/TESTING_PLAYBOOK.md` |
| Architecture-as-code | `docs/architecture/camada-testes/architecture-as-code.json` |
| Schema de relatório | `docs/contracts/camada-testes-padrao-ouro.schema.json` |
| Validador | `scripts/camada_testes_padrao_ouro.py` |
| Testes do validador | `tests/test_camada_testes_padrao_ouro.py` |
| Workflow | `.github/workflows/camada-testes-padrao-ouro.yml` |
| Relatório | `audit/camada-testes/camada-testes-padrao-ouro-report.json` |

## Comandos locais

```bash
# Validar camada de testes (report-only)
python scripts/camada_testes_padrao_ouro.py

# Suite de testes do validador
python -m pytest tests/test_camada_testes_padrao_ouro.py -v --tb=short

# Gates obrigatórios de merge (reprodução local)
cd backend && python -m pytest tests/ -v --tb=short --cov=app --cov-fail-under=60
cd frontend && npm run build
cd frontend && npx playwright test tests/e2e/responsividade.spec.js
```

## Semáforo do validador

| Estado | Condição | Decisão |
| --- | --- | --- |
| `passed` | Todas as camadas e governança OK | `continuar_incremento` |
| `passed_with_warnings` | Warnings sem erro duro | `revisar_warnings_antes_de_merge` |
| `failed` | Camada ou artefato obrigatório ausente | `corrigir_camada_testes` |

## Guardrails

- Modo padrão: `report_only` — não substitui CI ReqSys v2 Enterprise.
- Não altera thresholds de cobertura nem adiciona jobs bloqueantes por si só.
- Documentação deve refletir o estado real das árvores de teste.

## Relação com Trilha D

A Trilha D orquestra **dimensões** de qualidade (tests, coverage, mutation, contract, schema, ci-watch). Este runbook cobre a **camada transversal** de testes como artefato Tier 1 — mapa, convenções e validação estrutural.

Para incrementos de cobertura Pareto, usar [`coverage-targeted-tests-trilha-d.md`](coverage-targeted-tests-trilha-d.md).

## Evidência em PR

Incluir no corpo do PR:

- Comandos de teste executados.
- Jobs CI verdes (4 obrigatórios quando aplicável).
- Link para este runbook quando alterar estrutura da camada de testes.
