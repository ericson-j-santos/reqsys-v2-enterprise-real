# Menu Operacional — Coordenador Principal

**Data:** 2026-06-27  
**Escopo:** runbook enxuto para operação híbrida (automação fora dos chats + chats especializados como contexto).

## Princípio

| Camada | Papel |
|---|---|
| **Coordenador Principal** | Lê evidências, decide incremento, dispara execução allowlisted, escala para humano |
| **Chats fixos** (DevOps, QA, Arquitetura…) | Memória operacional, prompt-base, retomada por tema — **não** runtime autônomo |
| **GitHub Actions + scripts** | Execução repetível, auditável, com allowlist e guardrails |
| **Agente técnico / Cloud Agent** | Tarefas por branch/PR com escopo fechado |

Automação real fica **fora dos chats**. Chats consultados sob demanda; execução via workflows e agentes.

## Rotina diária (5 minutos)

1. Baixar artifacts da última execução (ou disparar leitura — ver menu abaixo).
2. Consolidar semáforo global.
3. Escolher **um** incremento objetivo.
4. Disparar agente técnico ou `workflow_dispatch` conforme tabela.
5. Registrar decisão no PR ou issue (não no chat como fonte única de verdade).

## Ordem de leitura (artifacts)

Ler nesta ordem; parar no primeiro **vermelho** bloqueante.

| # | Artifact | Arquivo canônico | Campo decisório |
|---|---|---|---|
| 1 | `operational-governance-orchestrator-evidence` | `operational-governance-orchestrator.json` | `state`, `decision`, `operational_score` |
| 2 | `runtime-health-validator-evidence` | `runtime-health-validator.json` | `state`, `executive_status`, `automatic_backlog` |
| 3 | `workflow-command-center-evidence` | `workflow-command-center.json` | falhas críticas, workflows ausentes |
| 4 | `pr-ci-watch-report` (por PR ativo) | `pr-ci-watch.json` | `decision`, `severity`, `score` |

Runbooks detalhados: [operational-governance-orchestrator](operational-governance-orchestrator.md), [runtime-health-validator](runtime-health-validator.md), [workflow-command-center](workflow-command-center.md), [pr-ci-watch](pr-ci-watch.md).

## Semáforo global

| Cor | Condição (qualquer uma) | Decisão |
|---|---|---|
| **Verde** | Orchestrator `state=green` **e** Health Validator `state=green` **e** sem PR crítico com `corrigir_falhas_*` | Continuar incremento planejado |
| **Amarelo** | Pendências, workflows ausentes na janela, `OPS-PENDING-*`, PR em `aguardar_finalizacao_*` | Validar logs/artifacts antes de merge; não promover produção |
| **Vermelho** | Orchestrator `state=red`, Health Validator `state=red`, CI obrigatório falho, `OPS-GAP-*` crítico | Bloquear merges; corrigir causa raiz primeiro |

### Backlog automático (Health Validator)

| Prefixo | Significado | Ação do coordenador |
|---|---|---|
| `OPS-AUTO-*` | Remediação allowlisted disponível (transitório) | Só em `mode=execute` após validar; preferir `dry_run` antes |
| `OPS-GAP-*` | Falha real; autocorreção bloqueada | Abrir PR/agente para correção manual |
| `OPS-PENDING-*` | Check ainda em execução | Aguardar ou disparar `PR CI Watch` |

## Menu fechado — `workflow_dispatch` seguro

Apenas estes workflows no ciclo normal. Demais workflows existem para governança profunda e **não** entram no menu diário.

### Leitura / consolidação (sempre seguro — `report_only`)

| Workflow | Inputs úteis | Artifact |
|---|---|---|
| **Operational Governance Orchestrator** | `branch=main` | `operational-governance-orchestrator-evidence` |
| **Runtime Health Validator** | `mode=report_only`, `branch=main` | `runtime-health-validator-evidence` |
| **Workflow Command Center** | sem dispatch (só monitor) | `workflow-command-center-evidence` |
| **Main Operational Health** | — | evidência em job summary |
| **Main Smoke CI** | — | `main-smoke-ci-evidence` |

### Por PR (escopo fechado)

| Workflow | Quando usar | Inputs |
|---|---|---|
| **PR CI Watch** | PR aberto/sincronizado; diagnóstico de checks | `pr_number`, `sha`, `comment=false` |
| **PR Evidence Gate** | Validar head SHA + workflows + artifacts | `pr_number` |
| **Governed PR Automation** | Validar elegibilidade de merge | `pr_number`, `execute_merge=false` |

### Remediação (cuidado — allowlist)

| Workflow | Modo padrão | Restrição |
|---|---|---|
| **Runtime Health Validator** | `dry_run` → depois `execute` | Só reruns allowlisted; **nunca** `failure` real |
| **Workflow Command Center** | dispatch opcional | Só: `main-smoke-ci.yml`, `main-operational-health.yml`, `pr-ci-watch.yml`, `ci-fast-operational.yml` |

### Merge (exige aprovação humana)

| Workflow | Pré-requisitos |
|---|---|
| **Governed PR Automation** | CI verde nos 6 gates, PR não-draft, mergeable, label `governed-merge-approved`, `execute_merge=true` |

Runbook: [governed-pr-automation](governed-pr-automation.md).

## Fluxo por incremento

```text
triagem (artifacts 1–2)
  → verde? continuar
  → amarelo? investigar + aguardar
  → vermelho? bloquear merge + corrigir

execução (agente técnico em cursor/<tema>-716c)
  → PR draft até CI verde

validação (artifacts 3–4 + CI obrigatório)
  → Backend Lint & Security
  → Backend Tests + Coverage
  → Frontend Build + Security Audit
  → Frontend Responsive E2E

evidência (artifacts no PR)
decisão humana (merge / deploy / produção)
```

Estados de entrega: [agile-runtime-workflow](../agile-runtime-workflow.md).

## O que o coordenador **não** faz

- Não trata chat fixo como agente autônomo paralelo.
- Não faz merge/deploy/produção sem label, gate e revisão quando sensível.
- Não dispara workflows fora do menu sem runbook explícito.
- Não ignora `OPS-GAP-*` com remediação `execute`.
- Não commita `backend/reqsys.db` modificado localmente.

Gates de produção: `docs/adr/ADR-0002-seguranca-gates-producao.md`, `AGENTS.md`.

## Consulta a chats especializados

| Tema | Quando consultar | Execução fica em |
|---|---|---|
| Arquitetura / ADR | Decisão estrutural, trade-off | PR + ADR em `docs/adr/` |
| DevOps / CI | Falha de pipeline, allowlist | Workflow + script |
| QA / E2E | Regressão visual/responsiva | Playwright + artifact |
| Segurança | Auth, CORS, JWT, conectores | Gates + revisão humana |
| Produto / backlog | Priorização de incremento | Issue/Project — não automático |

## Próximo incremento (template)

Preencher após cada ciclo:

```text
Semáforo: verde | amarelo | vermelho
Evidências lidas: <run_ids ou timestamps>
Bloqueio atual: <nenhum | OPS-GAP-xxx | CI falho>
Incremento escolhido: <1 frase>
Responsável: <agente/humano>
Disparo: <workflow ou branch>
Critério de pronto: <artifact + CI verde>
```

## Links rápidos

- Índice canônico: [00_INDICE_CANONICO.md](../00_INDICE_CANONICO.md)
- Runtime autônomo governado: [AUTONOMOUS_OPERATIONAL_RUNTIME.md](../ci/AUTONOMOUS_OPERATIONAL_RUNTIME.md)
- Governança de agentes: [AGENT_GOVERNANCE.md](../ai-governance/08-IA/AGENT_GOVERNANCE.md)
- Comandos locais e gotchas: [AGENTS.md](../../AGENTS.md)
