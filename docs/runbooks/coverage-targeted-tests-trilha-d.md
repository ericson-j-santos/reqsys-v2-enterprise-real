# Coverage Targeted Tests — Trilha D (Padrão Ouro)

**Data:** 2026-06-28  
**Incremento:** `coverage_targeted_tests`  
**Trilha:** D — Qualidade e Governança  
**Referência gate:** `OPS-GAP-COVERAGE` · `increment-type: hotfix`

## Objetivo

Elevar cobertura dos módulos críticos com menor percentual, concentrando esforço onde o Pareto Trilha D indica maior gap (`coverage` ≈ 74% → meta 82%).

Fonte Pareto: `docs/ops-dashboard/data/padrao-ouro-operational-pareto.json`

## Módulos alvo (prioridade)

| Módulo | Cobertura baseline | Meta incremental | Artefato de teste |
|---|---:|---:|---|
| `app/services/hub_lowcode.py` | ~14% | ≥ 45% | `test_hub_lowcode_service_critical_paths.py` |
| `app/services/wiki_publisher.py` | ~13% | ≥ 50% | `test_wiki_publisher_critical_paths.py` |
| `app/services/power_automate_provisioning.py` | ~74% | ≥ 80% | `test_power_automate_provisioning_critical_paths.py` |

Padrão de nome: `backend/tests/test_*_critical_paths.py`

## Gate de abertura

```bash
python3 scripts/agent_increment_gate.py \
  --status-json artifacts/coordenador-status/coordenador-status.json \
  --increment-type hotfix \
  --reference OPS-GAP-COVERAGE \
  --intent "coverage_targeted_tests"
```

## Implementação mínima

1. Testar **caminhos críticos** (degradação sem credenciais, gates de negócio, persistência local).
2. Preferir mocks de HTTP (`httpx`, `urllib`) — sem chamadas externas reais.
3. Não alterar comportamento de produção salvo bug evidenciado por teste.
4. Manter `pytest` verde e gate `--cov-fail-under=60`.

## Validação local

```bash
cd backend
python -m pytest tests/test_*_critical_paths.py -v --tb=short
python -m pytest tests/ -q --cov=app --cov-report=term-missing:skip-covered
```

Dimensão Trilha D isolada:

```bash
python scripts/trilha_d_qualidade_governanca.py --dimension coverage
```

## Monitoramento de CI (PR)

### Jobs obrigatórios (merge)

| Job | Workflow |
|---|---|
| Backend Lint & Security | CI — ReqSys v2 Enterprise |
| Backend Tests + Coverage | CI — ReqSys v2 Enterprise |
| Trilha D — coverage | Trilha D — Qualidade e Governança |
| Trilha D — tests | Trilha D — Qualidade e Governança |
| Pipeline Governança + Evidence Snapshot | CI — ReqSys v2 Enterprise |

### Comandos de monitoramento

```bash
# Listar PR da branch
gh pr list --head cursor/coverage-targeted-tests-09bf

# Status consolidado dos checks
gh pr checks <numero_pr>

# Acompanhar até concluir
gh pr checks <numero_pr> --watch

# Falhas detalhadas
gh run view <run_id> --log-failed
```

### Sem PR aberto (branch `cursor/*`)

O workflow **Padrão Ouro Delivery Automation** tenta abrir PR draft automaticamente no push.

```bash
gh run list --branch cursor/coverage-targeted-tests-09bf --limit 5
gh run view <run_id> --json jobs,conclusion
```

Metadata de PR: `.github/pr-metadata/cursor-coverage-targeted-tests-09bf.json`

### Semáforo esperado

| Estado CI | Decisão |
|---|---|
| Todos jobs obrigatórios `success` | Marcar PR ready → merge governado |
| Trilha D coverage `failure` | Ampliar testes nos módulos com `term-missing` |
| Lint `failure` | `ruff check app/ --select E,F,W,I --ignore E501` |
| Pipeline Governança `bloqueado` | Corrigir job falho upstream primeiro |

## Evidências pós-merge

1. Atualizar `docs/ops-dashboard/data/trilha-d-history.json` (workflow Trilha D publica histórico).
2. Reexecutar `scripts/build_padrao-ouro_operational_pareto.py` se score coverage mudou materialmente.
3. Registrar no PR: cobertura total antes/depois e módulos tocados.

## Critério de pronto

| Critério | Estado |
|---|---|
| Novos `test_*_critical_paths.py` | Commitados |
| Cobertura total backend | ≥ 82% (meta incremental) ou +2pp vs baseline |
| `pytest` completo | Verde |
| Trilha D dimensão `coverage` | `passed` |
| CI Enterprise | Verde |
| PR | Mergeado em `main` |

## Rollback

Reverter merge do PR — apenas testes adicionados; sem impacto em runtime.

## Referências Tier 1

- [`trilha-d-qualidade-governanca.md`](trilha-d-qualidade-governanca.md)
- [`docs/padrao-ouro/ENGINEERING_PLAYBOOKS.md`](../padrao-ouro/ENGINEERING_PLAYBOOKS.md) — Corrigir CI
- [`docs/adr/ADR-039-trilha-d-qualidade-governanca.md`](../adr/ADR-039-trilha-d-qualidade-governanca.md)
- [`AGENTS.md`](../../AGENTS.md) — comandos canônicos pytest
