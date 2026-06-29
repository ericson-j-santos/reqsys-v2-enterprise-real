# Engineering Playbooks — Fluxos Operacionais

Data de referência: 2026-06-27

Índice de playbooks operacionais para agentes, automações e engenheiros. Cada playbook descreve um fluxo executável com pré-condições, passos, evidências e rollback.

## Como usar

| Cenário | Playbook |
| --- | --- |
| Abrir novo incremento/PR | [Abrir incremento](#1-abrir-incremento) |
| Corrigir CI vermelho | [Corrigir CI](#2-corrigir-ci) |
| Adicionar / estruturar testes | [Testing layer](#8-camada-de-testes) |
| Merge governado | [Governed merge](#3-governed-merge) |
| Validar evidências | [Evidence validation](#4-evidence-validation) |
| Release governance | [Release governance](#5-release-governance) |
| Criar analytics | [Criar analytics](#6-criar-analytics) |
| Onboarding agente | [Onboarding agente/IA](#7-onboarding-agenteia) |

---

## 1. Abrir incremento

**Objetivo:** Iniciar frente nova com governança e sem conflito com incrementos ativos.

### Pré-condições

- Ler [`docs/padrao-ouro/README.md`](README.md) e [`living-architecture-index.json`](living-architecture-index.json).
- Verificar ownership do domínio em [LIVING_ARCHITECTURE_INDEX.md](LIVING_ARCHITECTURE_INDEX.md#ownership-matrix).

### Passos

```text
1. python3 scripts/agent_increment_gate.py --increment-type new_front --intent "<objetivo>"
   └── exit 0 = permitido | exit 1 = bloqueado (seguir recommended_actions)

2. git checkout -b cursor/<descricao>-a152

3. Implementar mudança mínima no escopo declarado

4. Validar localmente:
   - Backend: cd backend && pytest tests/ -v --tb=short
   - Frontend: cd frontend && npm run build

5. Commit + push + abrir PR

6. Aguardar CI completo (4 jobs obrigatórios)
```

### Evidências obrigatórias

- Objetivo, escopo e fora de escopo no PR.
- Testes executados.
- ADR se decisão transversal.

### Runbooks

- [`docs/runbooks/agent-increment-gate.md`](../runbooks/agent-increment-gate.md)
- [`docs/runbooks/coordenador-principal-menu-operacional.md`](../runbooks/coordenador-principal-menu-operacional.md)
- [`docs/runbooks/governed-pr-automation.md`](../runbooks/governed-pr-automation.md)

---

## 2. Corrigir CI

**Objetivo:** Restaurar pipeline verde com diagnóstico rastreável.

### Passos

```text
1. Identificar job falho no workflow "CI — ReqSys v2 Enterprise"
   ├── Backend Lint & Security (ruff + pip-audit + bandit)
   ├── Backend Tests + Coverage (pytest)
   ├── Frontend Build + Security Audit
   └── Frontend Responsive E2E (Playwright)

2. Reproduzir localmente com comando canônico (ver AGENTS.md)

3. Corrigir com diff mínimo

4. Se falha intermitente: consultar failure-pattern-engine artifacts

5. Documentar evidência em docs/evidence/ se recorrente
```

### Runbooks

- [`docs/runbooks/main-smoke-ci.md`](../runbooks/main-smoke-ci.md)
- [`docs/runbooks/ci-fast-deep-review.md`](../runbooks/ci-fast-deep-review.md)
- [`docs/runbooks/monitorador-apis-python-ci.md`](../runbooks/monitorador-apis-python-ci.md)
- [`docs/runbooks/pr-ci-watch.md`](../runbooks/pr-ci-watch.md)

---

## 3. Governed merge

**Objetivo:** Merge controlado com evidência e sem regressão.

### Pré-condições

- CI completo verde (4 jobs).
- Sem blockers em `coordenador-status.json`.
- PR não em draft.

### Passos

```text
1. Revisar escopo vs. diff
2. Verificar ADR/contrato se aplicável
3. Confirmar evidências no PR
4. Merge via merge queue governada (quando ativa)
5. Pós-merge: validar main-operational-post-merge-health
```

### Runbooks

- [`docs/runbooks/governed-merge-queue.md`](../runbooks/governed-merge-queue.md)
- [`docs/runbooks/main-post-merge-validation.md`](../runbooks/main-post-merge-validation.md)
- [`docs/runbooks/main-operational-post-merge-health.md`](../runbooks/main-operational-post-merge-health.md)
- [`docs/runbooks/post-merge-operational-maturity-matrix.md`](../runbooks/post-merge-operational-maturity-matrix.md)

---

## 4. Evidence validation

**Objetivo:** Garantir rastreabilidade e evidência mínima antes de considerar entrega pronta.

### Passos

```text
1. Verificar artifact-contract-validation (report-only)
2. Verificar living-architecture-traceability (links internos)
3. Consultar operational-evidence-hub
4. Validar correlation_id em logs/auditoria
5. Registrar evidência em docs/evidence/ quando relevante
```

### Runbooks

- [`docs/runbooks/pr-evidence-gate.md`](../runbooks/pr-evidence-gate.md)
- [`docs/runbooks/operational-evidence-hub.md`](../runbooks/operational-evidence-hub.md)
- [`docs/runbooks/public-runtime-evidence-gate.md`](../runbooks/public-runtime-evidence-gate.md)
- [`docs/runbooks/living-architecture-traceability.md`](../runbooks/living-architecture-traceability.md)

---

## 5. Release governance

**Objetivo:** Promover release com gates de produção e rollback definido.

### Pré-condições

- Gates de produção (ADR-0002) verificados.
- `ALLOW_DEMO_LOGIN=false` em prod.
- JWT issuer/audience configurados.
- CORS não é `*`.

### Passos

```text
1. Promover: dev → staging → prod (ordem obrigatória)
2. Executar golden-release-readiness
3. Validar endpoint afetado no ambiente publicado
4. Registrar release note em docs/releases/
5. Validar pós-merge operacional
```

### Runbooks

- [`docs/runbooks/golden-release-operational-checklist.md`](../runbooks/golden-release-operational-checklist.md)
- [`docs/runbooks/fly-governed-command-center.md`](../runbooks/fly-governed-command-center.md)
- [`docs/runbooks/fly-runtime-p0.md`](../runbooks/fly-runtime-p0.md)
- [`docs/runbooks/fly-runtime-p0-pos-deploy-evidencia.md`](../runbooks/fly-runtime-p0-pos-deploy-evidencia.md)

---

## 6. Criar analytics

**Objetivo:** Adicionar indicador analítico com drill-down schema-driven.

### Passos

```text
1. Definir schema do indicador (ADR-0006)
2. Implementar fluxo: Indicador → gráfico → analítico → ação
3. Registrar contrato se artifact JSON
4. Validar responsividade (desktop/tablet/mobile)
5. Conectar ao dashboard operacional relevante
```

### Runbooks

- [`docs/runbooks/ci-lead-time-analytics.md`](../runbooks/ci-lead-time-analytics.md)
- [`docs/runbooks/runtime-predictive-analytics.md`](../runbooks/runtime-predictive-analytics.md)
- [`docs/runbooks/operational-analytics-engine.md`](../runbooks/operational-analytics-engine.md)
- [`docs/runbooks/github-runtime-analytics.md`](../runbooks/github-runtime-analytics.md)

---

## 8. Camada de testes

**Objetivo:** Adicionar ou estruturar testes alinhados à pirâmide Padrão Ouro e aos gates de CI.

### Pré-condições

- Ler [`TESTING_PLAYBOOK.md`](TESTING_PLAYBOOK.md) e módulo afetado em `living-architecture-index.json`.

### Passos

```text
1. Identificar camada: backend pytest | frontend vitest | playwright | governança
2. Seguir convenção de nomenclatura (test_<modulo>.py, *.test.js, *.spec.js)
3. Validar localmente com comando canônico (ver TESTING_PLAYBOOK)
4. Se cobertura crítica: docs/runbooks/coverage-targeted-tests-trilha-d.md
5. Evidenciar comandos no PR
6. Validar estrutura: python scripts/camada_testes_padrao_ouro.py
```

### Runbooks

- [`docs/padrao-ouro/TESTING_PLAYBOOK.md`](TESTING_PLAYBOOK.md)
- [`docs/runbooks/camada-testes-padrao-ouro.md`](../runbooks/camada-testes-padrao-ouro.md)
- [`docs/runbooks/coverage-targeted-tests-trilha-d.md`](../runbooks/coverage-targeted-tests-trilha-d.md)
- [`docs/runbooks/trilha-d-qualidade-governanca.md`](../runbooks/trilha-d-qualidade-governanca.md)
- [`docs/SECURITY_GATES_TEST_MATRIX.md`](../SECURITY_GATES_TEST_MATRIX.md)

---

## 7. Onboarding agente/IA

**Objetivo:** Contexto reutilizável para agente executar incremento com precisão arquitetural.

### Ordem de leitura

```text
1. AGENTS.md                          → comandos, gotchas, serviços canônicos
2. docs/padrao-ouro/README.md         → hub Tier 1
3. living-architecture-index.json     → módulos, ownership, extensão
4. docs/padrao-ouro/ADR_INDEX.md        → decisões fundacionais (0001–0006)
5. docs/padrao-ouro/CONTRACT_CATALOG.md → contratos do domínio afetado
6. docs/padrao-ouro/TESTING_PLAYBOOK.md → camada de testes (se alterar testes)
7. docs/runbooks/coordenador-principal-menu-operacional.md → menu operacional
8. Executar agent_increment_gate antes de criar branch
```

### Referências IA

- [`docs/ai-governance/INDEX.md`](../ai-governance/INDEX.md)
- [`docs/ai-governance/08-IA/MULTIAGENT_STANDARD.md`](../ai-governance/08-IA/MULTIAGENT_STANDARD.md)
- [`docs/ai-governance/08-IA/ARQUITETURA_MULTIAGENTE_ENTERPRISE.md`](../ai-governance/08-IA/ARQUITETURA_MULTIAGENTE_ENTERPRISE.md)
- [`docs/ai-governance/08-IA/agents/README.md`](../ai-governance/08-IA/agents/README.md)
- [`docs/ai-governance/09-CHECKLISTS/PR_CHECKLIST.md`](../ai-governance/09-CHECKLISTS/PR_CHECKLIST.md)

---

## Índice completo de runbooks (~85)

### Governança e PR

| Runbook | Caminho |
| --- | --- |
| Agent Increment Gate | `docs/runbooks/agent-increment-gate.md` |
| Coordenador Principal | `docs/runbooks/coordenador-principal-menu-operacional.md` |
| Governed PR Automation | `docs/runbooks/governed-pr-automation.md` |
| Governed Merge Queue | `docs/runbooks/governed-merge-queue.md` |
| PR Evidence Gate | `docs/runbooks/pr-evidence-gate.md` |
| PR Quality Review | `docs/runbooks/pr-quality-review.md` |
| PR Auto Recovery V3 | `docs/runbooks/pr-auto-recovery-v3-controlled.md` |

### CI e qualidade

| Runbook | Caminho |
| --- | --- |
| Main Smoke CI | `docs/runbooks/main-smoke-ci.md` |
| CI Fast Deep Review | `docs/runbooks/ci-fast-deep-review.md` |
| CI Lead Time Analytics | `docs/runbooks/ci-lead-time-analytics.md` |
| CI Router | `docs/runbooks/ci-router.md` |
| Dashboard Regression | `docs/runbooks/dashboard-regression-validation.md` |
| Coverage Targeted Tests (Trilha D) | `docs/runbooks/coverage-targeted-tests-trilha-d.md` |
| Camada de Testes — Padrão Ouro | `docs/runbooks/camada-testes-padrao-ouro.md` |

### Operações e runtime

| Runbook | Caminho |
| --- | --- |
| Operational Health Dashboard | `docs/runbooks/operational-health-dashboard.md` |
| Operational Evidence Hub | `docs/runbooks/operational-evidence-hub.md` |
| Operational Governance Orchestrator | `docs/runbooks/operational-governance-orchestrator.md` |
| Runtime Operational Health | `docs/runbooks/runtime-operational-health.md` |
| Runtime Health Validator | `docs/runbooks/runtime-health-validator.md` |
| Ops Dashboard | `docs/runbooks/ops-dashboard.md` |

### Trilhas Padrão Ouro

| Runbook | Caminho |
| --- | --- |
| Trilhas Consolidadas | `docs/runbooks/trilhas-padrao-ouro.md` |
| Trilha A — Runtime Público | `docs/runbooks/trilha-a-runtime-publico.md` |
| Trilha B — Observabilidade | `docs/runbooks/trilha-b-observabilidade-enterprise.md` |
| Trilha C — UX Operacional | `docs/runbooks/trilha-c-ux-operacional.md` |
| Trilha D — Qualidade | `docs/runbooks/trilha-d-qualidade-governanca.md` |
| Trilha E — Arquitetura Viva | `docs/runbooks/trilha-e-arquitetura-viva.md` |
| Living Architecture Traceability | `docs/runbooks/living-architecture-traceability.md` |

### Delivery e release

| Runbook | Caminho |
| --- | --- |
| Delivery Evidence Index | `docs/runbooks/delivery-evidence-index.md` |
| Delivery Status Report | `docs/runbooks/delivery-status-report.md` |
| Golden Release Checklist | `docs/runbooks/golden-release-operational-checklist.md` |
| Fly Governed Command Center | `docs/runbooks/fly-governed-command-center.md` |
| Fly Runtime P0 Pós-Deploy | `docs/runbooks/fly-runtime-p0-pos-deploy-evidencia.md` |

---

## Ciclo operacional canônico

```text
triagem → ajuste mínimo → CI completo → evidência → merge controlado → validação pós-merge → fechamento de duplicados
```

## Referências

- Hub Tier 1: [`docs/padrao-ouro/README.md`](README.md)
- AGENTS.md: [`AGENTS.md`](../../AGENTS.md)
- Índice canônico: [`docs/00_INDICE_CANONICO.md`](../00_INDICE_CANONICO.md)
