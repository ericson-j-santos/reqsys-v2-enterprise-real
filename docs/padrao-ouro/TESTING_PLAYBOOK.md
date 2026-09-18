# Testing Playbook — Camada de Testes Padrão Ouro (Tier 1)

Data de referência: 2026-06-29

Playbook canônico da **camada de testes** do ReqSys v2 Enterprise. Consolida pirâmide, árvores, gates, convenções, comandos e evidências — navegável por humanos, agentes e automações.

## Princípio

Testes aqui **não são scripts soltos** — são infraestrutura de qualidade versionada, rastreável e alinhada ao ciclo Padrão Ouro:

```text
triagem → ajuste mínimo → CI completo → evidência → merge controlado → validação pós-merge
```

## Pirâmide de testes

| Camada | Local | Runner | Gate merge | Modo |
| --- | --- | --- | --- | --- |
| **Unitário backend** | `backend/tests/` | pytest | Sim (`ci.yml`) | SQLite demo, mocks |
| **Unitário frontend** | `frontend/src/**/__tests__/` | Vitest | Não (local/PR) | jsdom, Pinia/Vuetify |
| **Integração / API** | `backend/tests/` | pytest + TestClient | Sim | FastAPI in-process |
| **E2E responsivo** | `frontend/tests/e2e/` | Playwright | Sim (quando roteado) | API mocks |
| **E2E funcional** | `frontend/tests/e2e/` | Playwright | Não (local) | Backend real |
| **Governança / ops** | `tests/` (raiz) | pytest | Workflows dedicados | Scripts, contratos, trilhas |
| **Frontends alternativos** | `e2e/` (raiz) | Playwright | Não (`validar_qualidade.sh`) | Vuetify + Angular |

## Árvores de teste

### 1. Backend — `backend/tests/`

| Padrão | Exemplo | Quando usar |
| --- | --- | --- |
| Espelho de domínio | `test_requisitos.py` | CRUD e regras de negócio |
| Caminhos críticos | `test_*_critical_paths.py` | Módulos com baixa cobertura (Pareto Trilha D) |
| Security gates | `test_security_*_individual.py` | Gates de produção (ADR-0002) |
| Contrato | `test_*_contract.py` | Schemas, artifacts, OpenAPI |
| Smoke público | `test_public_smoke_routes.py` | Rotas de health/smoke |

**Fixtures canônicas:** `conftest.py` — `client`, `token`, `auth_headers`.

**Cobertura:**
- Gate obrigatório: **60%** (`--cov-fail-under=60`)
- Meta Padrão Ouro (Trilha D Pareto): **~82%**
- Omits configurados: `app/db.py`, `app/models/*`, `app/schemas/*`

### 2. Frontend unitário — `frontend/src/`

| Padrão | Exemplo | Quando usar |
| --- | --- | --- |
| Co-localizado | `src/utils/filtros.test.js` | Utilitários puros |
| `__tests__/` | `src/stores/__tests__/auth.test.js` | Stores, services, composables |
| Smoke de views | `src/views/__tests__/views.smoke.test.js` | Montagem de todas as views |

**Setup:** `frontend/src/test/setup.js` (Vuetify, Pinia, polyfills).

### 3. Frontend E2E — `frontend/tests/e2e/`

| Spec | Gate CI | Dependência |
| --- | --- | --- |
| `responsividade.spec.js` | **Obrigatório** (quando roteado) | API mocks (`helpers/responsiveMocks.js`) |
| `login.spec.js` | Local | Backend real (`helpers/auth.js`) |
| `dashboard.spec.js`, `requisitos.spec.js`, etc. | Local | Backend real |

**Marcadores:** `data-testid` por rota (`route-dashboard`, `route-requisitos`, …).

### 4. Governança — `tests/` (raiz do repositório)

Valida scripts, workflows, contratos, trilhas e coordenador — **não confundir** com `backend/tests/`.

Exemplos: `test_trilha_d_qualidade_governanca.py`, `test_pr_ci_watch.py`, `test_openapi_semantic_diff.py`.

### 5. Frontends alternativos — `e2e/` (raiz)

Playwright para `frontend-vuetify` e `frontend-angular`. Executado via `scripts/validar_qualidade.sh`, fora do gate principal de merge.

---

## Gates de CI obrigatórios (merge)

Workflow: `.github/workflows/ci.yml` — **CI — ReqSys v2 Enterprise**

| Job | Comando canônico |
| --- | --- |
| Backend Lint & Security | `ruff`, `pip-audit`, `bandit` |
| Backend Tests + Coverage | `pytest tests/ --cov=app --cov-fail-under=60` |
| Frontend Build + Security Audit | `npm ci`, `npm audit --audit-level=high`, `npm run build` |
| Frontend Responsive E2E | `npx playwright test tests/e2e/responsividade.spec.js` |

### Trilha D (complementar, report-only)

Workflow: `.github/workflows/trilha-d-qualidade-governanca.yml`

Dimensões: `tests`, `coverage`, `mutation`, `contract`, `schema`, `ci-watch`.

Não substitui o CI principal; consolida matriz paralelizável de qualidade.

---

## Como usar

| Situação | Ação |
| --- | --- |
| Novo endpoint / service backend | `test_<modulo>.py` espelhando `app/` |
| Módulo com cobertura baixa | `test_<modulo>_critical_paths.py` (ver runbook Trilha D) |
| Nova view / rota frontend | Adicionar rota em `rotasResponsivas.js` + spec responsivo |
| Novo contrato JSON | Teste `*contract*` + schema em `docs/contracts/` |
| Corrigir CI vermelho | [ENGINEERING_PLAYBOOKS §2](ENGINEERING_PLAYBOOKS.md#2-corrigir-ci) |
| Evidência de PR | Listar comandos executados e jobs verdes |

---

## Fluxos operacionais

### Adicionar teste backend

```text
1. Identificar módulo em backend/app/ (living-architecture-index.json)
2. Criar ou estender backend/tests/test_<modulo>.py
3. Usar fixture client/token de conftest.py
4. Validar: cd backend && python -m pytest tests/test_<modulo>.py -v --tb=short
5. Se cobertura crítica: seguir docs/runbooks/coverage-targeted-tests-trilha-d.md
```

### Adicionar teste frontend unitário

```text
1. Criar src/<area>/__tests__/<nome>.test.js
2. Importar setup global (automático via vite.config.js)
3. Validar: cd frontend && npm run test:unit
```

### Adicionar rota ao gate responsivo

```text
1. Registrar rota em frontend/src/constants/rotasResponsivas.js (data-testid)
2. Garantir mock em tests/e2e/helpers/responsiveMocks.js
3. Validar: npx playwright test tests/e2e/responsividade.spec.js
```

### Evidência mínima em PR

- Comandos de teste executados (backend pytest, frontend build, E2E se aplicável).
- Escopo coberto vs. fora de escopo.
- Risco e rollback quando alterar comportamento observável.

---

## Comandos canônicos

```bash
# Backend — suite completa
cd backend && python -m pytest tests/ -v --tb=short

# Backend — com cobertura (gate CI)
cd backend && python -m pytest tests/ -v --tb=short --cov=app --cov-report=term-missing --cov-fail-under=60

# Backend — caminhos críticos
cd backend && python -m pytest tests/test_*_critical_paths.py -v --tb=short

# Frontend — unitário
cd frontend && npm run test:unit

# Frontend — E2E responsivo (gate CI)
cd frontend && npx playwright test tests/e2e/responsividade.spec.js

# Frontend — E2E com backend (local)
cd frontend && node scripts/run-e2e-safe.js

# Trilha D — dimensão isolada
python scripts/trilha_d_qualidade_governanca.py --dimension coverage

# Camada de testes — validador Padrão Ouro (report-only)
python scripts/camada_testes_padrao_ouro.py

# Qualidade local consolidada
bash scripts/validar_qualidade.sh
```

---

## Convenções

| Aspecto | Convenção |
| --- | --- |
| Nome arquivo backend | `test_<feature>.py`; sufixo `_critical_paths` para Pareto |
| Nome arquivo frontend unit | `<nome>.test.js` ou `__tests__/<nome>.test.js` |
| Nome spec E2E | `<feature>.spec.js` |
| Auth em testes | Login demo via e-mail; fixture `token` module-scoped |
| Mocks externos | Sem HTTP real para Azure/Redmine/SSRS em CI |
| Segredos | Placeholders (`placeholder`, `example.com`); nunca PII real |
| Correlation ID | Preservar em testes de auditoria quando aplicável |

---

## Relação com Trilhas e Tier 1

| Artefato | Relação |
| --- | --- |
| [Trilha D](../runbooks/trilha-d-qualidade-governanca.md) | Orquestra dimensões de qualidade (matrix CI) |
| [ENGINEERING_PLAYBOOKS](ENGINEERING_PLAYBOOKS.md) | Fluxos de incremento, CI e merge |
| [CONTRACT_CATALOG](CONTRACT_CATALOG.md) | Schemas validados por testes `*contract*` |
| [SECURITY_GATES_TEST_MATRIX](../SECURITY_GATES_TEST_MATRIX.md) | Mapeamento gate ↔ arquivo de teste |
| [coverage-targeted-tests-trilha-d](../runbooks/coverage-targeted-tests-trilha-d.md) | Incremento Pareto de cobertura |

---

## Ownership

| Área | Owner | ADR |
| --- | --- | --- |
| Backend tests | Backend Core | [ADR-0004](../adr/ADR-0004-ci-cd-qualidade.md) |
| Frontend tests | Frontend Core | [ADR-0004](../adr/ADR-0004-ci-cd-qualidade.md) |
| Trilha D / qualidade | Quality Governance | [ADR-039](../adr/ADR-039-trilha-d-qualidade-governanca.md) |
| Camada de testes Tier 1 | Architecture Governance | [ADR-0004](../adr/ADR-0004-ci-cd-qualidade.md) |

---

## Manutenção

Atualizar este playbook quando houver:

- Nova árvore de teste ou runner.
- Novo gate obrigatório em `ci.yml`.
- Mudança de threshold de cobertura.
- Novo padrão de nomenclatura ou fixture compartilhada.

Validação report-only: workflow [`Camada de Testes — Padrão Ouro`](../../.github/workflows/camada-testes-padrao-ouro.yml).

## Referências

- [`docs/runbooks/camada-testes-padrao-ouro.md`](../runbooks/camada-testes-padrao-ouro.md) — runbook operacional.
- [`docs/architecture/camada-testes/architecture-as-code.json`](../architecture/camada-testes/architecture-as-code.json) — manifesto machine-readable.
- [`AGENTS.md`](../../AGENTS.md) — comandos e gotchas para agentes.
