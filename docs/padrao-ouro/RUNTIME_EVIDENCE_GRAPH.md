# Runtime Evidence Graph

Data de referência: 2026-06-27

Grafo operacional que conecta **workflows → PRs → artifacts → métricas → dashboards → analytics** para governança evidence-driven e troubleshooting acelerado.

## Objetivo

Transformar evidências dispersas em um grafo navegável que permite:

- Rastrear de um PR até os artifacts e métricas gerados.
- Identificar regressões indiretas entre incrementos paralelos.
- Orientar agentes/IA com contexto operacional reutilizável.
- Acelerar troubleshooting de CI e governança.

## Entregas runtime

| Artefato | Caminho | Formato |
| --- | --- | --- |
| Evidence Graph (JSON) | `reports/github-runtime-analytics/runtime-operational-evidence-graph.json` | Grafo estruturado |
| Evidence Graph (MD) | `reports/github-runtime-analytics/runtime-operational-evidence-graph.md` | Relatório legível |
| Correlation Timeline | `reports/github-runtime-analytics/runtime-operational-correlation-timeline.json` | Pré-requisito do grafo |

## Pipeline de geração

```text
GitHub Actions runs + PRs
        │
        ▼
generate_runtime_operational_correlation_timeline.py
        │
        ▼
runtime-operational-correlation-timeline.json
        │
        ▼
generate_runtime_operational_evidence_graph.py
        │
        ├── runtime-operational-evidence-graph.json
        └── runtime-operational-evidence-graph.md
```

### Workflow

- **Arquivo:** `.github/workflows/runtime-operational-evidence-graph.yml`
- **Trigger:** PR em `tools/product_intelligence/**`, `docs/operations/**`
- **Modo:** report-only (sem deploy, sem mutação produtiva)
- **Scripts:** `tools/product_intelligence/generate_runtime_operational_*.py`

## Nós do grafo

| Tipo de nó | Exemplos | Fonte |
| --- | --- | --- |
| **Workflow** | `ci.yml`, `pr-evidence-gate`, `coordenador-status-consolidator` | `.github/workflows/` |
| **PR** | PR145, PR225 | GitHub API / evidências versionadas |
| **Artifact** | `ci-evidence`, `coordenador-status.json`, `living-architecture-traceability-report` | Workflow artifacts |
| **Métrica** | CI lead time, maturity score, operational risk | `audit/` e `reports/` |
| **Dashboard** | ops-dashboard, evidence-hub, command-center | `docs/dashboard/`, `docs/ops-dashboard/` |
| **Evidência** | `docs/evidence/*.md`, `docs/operations/ci-evidence-refresh-*.md` | Documentação versionada |

## Conexões principais

```text
                    ┌─────────────────┐
                    │   PR (feature)  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────────┐
        │ CI Fast  │  │ Evidence │  │ Agent Incr.  │
        │ ci.yml   │  │ Gate     │  │ Gate         │
        └────┬─────┘  └────┬─────┘  └──────┬───────┘
             │             │               │
             ▼             ▼               ▼
        ci-evidence   pr-evidence    coordenador-status
             │             │               │
             └─────────────┼───────────────┘
                           ▼
              ┌────────────────────────┐
              │ Evidence Graph (JSON)  │
              └────────────┬───────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ops-dashboard  evidence-hub  command-center
```

## Índices relacionados

| Índice | Caminho | Relação |
| --- | --- | --- |
| Living Architecture Map | `docs/traceability/living-architecture-map.json` | Workflows, artifacts, dashboards |
| Artifact Contracts Index | `docs/contracts/artifact-contracts-index.md` | Contratos de artifacts |
| Governance Evidence Index | `docs/ops-dashboard/governance-evidence-index.md` | Evidências de governança |
| Command Center Evidence | `docs/dashboard/command-center-evidence-index.md` | Evidências de delivery |
| Product Intelligence Evidence | `docs/product/PRODUCT_INTELLIGENCE_FINAL_EVIDENCE_INDEX.md` | Evidências PI |

## Guardrails

- Sem deploy produtivo.
- Sem mutação de secrets/permissões.
- Sem escrita externa.
- Revisão humana obrigatória para ações derivadas do grafo.
- Modo report-only até promoção formal para enforced.

## Como usar para troubleshooting

| Sintoma | Caminho no grafo |
| --- | --- |
| CI vermelho pós-merge | PR → ci.yml → ci-evidence → `docs/operations/ci-evidence-refresh-*.md` |
| Agent bloqueado | coordenador-status-consolidator → coordenador-status.json → `increment_gate.blockers` |
| Artifact inválido | operational-artifact-schema-validation → contract-validation-report |
| Dashboard desatualizado | artifact-discovery-index → health.json → ops-dashboard |
| Conflito entre PRs | PR nodes → overlapping workflows → ownership matrix |

## Próximo incremento recomendado

**Runtime Evidence Graph Dashboard Integration** — integrar grafo e UI ao Ops Dashboard e Operational Evidence Hub (ver [`docs/operations/RUNTIME_OPERATIONAL_EVIDENCE_UI.md`](../operations/RUNTIME_OPERATIONAL_EVIDENCE_UI.md)).

## Referências

- Documentação original: [`docs/operations/RUNTIME_OPERATIONAL_EVIDENCE_GRAPH.md`](../operations/RUNTIME_OPERATIONAL_EVIDENCE_GRAPH.md)
- Correlation Timeline: [`docs/operations/RUNTIME_OPERATIONAL_CORRELATION_TIMELINE.md`](../operations/RUNTIME_OPERATIONAL_CORRELATION_TIMELINE.md)
- GitHub Runtime Analytics: [`docs/operations/GITHUB_RUNTIME_ANALYTICS.md`](../operations/GITHUB_RUNTIME_ANALYTICS.md)
- Hub Tier 1: [`docs/padrao-ouro/README.md`](README.md)
