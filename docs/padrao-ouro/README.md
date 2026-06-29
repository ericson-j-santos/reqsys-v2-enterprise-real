# Padrão Ouro — Infraestrutura de Documentação Viva (Tier 1)

Data de referência: 2026-06-27

Este hub consolida a documentação operacional de **máximo ROI** para o ReqSys v2 Enterprise Real: múltiplos PRs paralelos, governança automatizada, CI orchestration, agentes e evolução contínua pós-merge.

## Princípio

Documentação aqui **não é texto morto** — é infraestrutura operacional viva, versionada e navegável por humanos, agentes e automações.

## Tier 1 — Altíssimo ROI

| # | Artefato | Caminho | Finalidade |
| --- | --- | --- | --- |
| 1 | **Living Architecture Index** | [`LIVING_ARCHITECTURE_INDEX.md`](LIVING_ARCHITECTURE_INDEX.md) | Mapa navegável de módulos, fluxos, pipelines, ownership, eventos, dependências e dashboards. |
| 2 | **ADR Index** | [`ADR_INDEX.md`](ADR_INDEX.md) | Catálogo de decisões arquiteturais com problema, decisão, impacto e evidência. |
| 3 | **Runtime Evidence Graph** | [`RUNTIME_EVIDENCE_GRAPH.md`](RUNTIME_EVIDENCE_GRAPH.md) | Grafo que conecta workflows, PRs, artifacts, métricas e dashboards. |
| 4 | **Contract Catalog** | [`CONTRACT_CATALOG.md`](CONTRACT_CATALOG.md) | Inventário de schemas, eventos, APIs, payloads e pipelines. |
| 5 | **Engineering Playbooks** | [`ENGINEERING_PLAYBOOKS.md`](ENGINEERING_PLAYBOOKS.md) | Fluxos operacionais para incrementos, CI, merge governado e evidências. |
| 6 | **Testing Playbook** | [`TESTING_PLAYBOOK.md`](TESTING_PLAYBOOK.md) | Pirâmide, árvores, gates, convenções e comandos da camada de testes. |


## Foco operacional Padrão Ouro

Enquanto o gate de incremento estiver em modo de consolidação, o foco Padrão Ouro deve priorizar estabilização e rastreabilidade, sem abrir nova frente concorrente. Use a sequência abaixo como checklist curto para agentes e revisores:

| Prioridade | Foco | Evidência esperada | Artefato de apoio |
| --- | --- | --- | --- |
| P0 | Consolidar incremento ativo | Gate `consolidate` permitido e pendências críticas registradas | `artifacts/coordenador-status/coordenador-status.json` |
| P1 | Validar contratos e paths vivos | JSONs carregáveis, links internos e schemas sem drift | `living-architecture-index.json`, `docs/traceability/living-architecture-map.json` |
| P2 | Preservar CI e testes mínimos | Comando focado executado ou limitação documentada | `TESTING_PLAYBOOK.md` |
| P3 | Atualizar documentação operacional | README, runbook, ADR ou release note atualizado quando houver impacto | `ENGINEERING_PLAYBOOKS.md` |

Critério de saída: uma mudança Padrão Ouro só deve ser considerada pronta quando a evidência de gate, os artefatos Tier 1 afetados e o comando de validação focado estiverem rastreáveis no PR.

## Índices machine-readable

| Artefato | Caminho | Uso |
| --- | --- | --- |
| Living Architecture Index (JSON) | [`living-architecture-index.json`](living-architecture-index.json) | Contexto reutilizável para agentes/IA — módulos, ownership, pontos de extensão. |
| Matriz de ambientes Fly.io | [`../../infra/fly-environments.json`](../../infra/fly-environments.json) | Apps, URLs, volumes, smoke endpoints e promoção dev → hml → prod. |
| URLs públicas canônicas | [`../../infra/public-access-urls.json`](../../infra/public-access-urls.json) | Alvos de validação Fly/DuckDNS para `validar-acessos-publicos.mjs`. |
| Mapa de rastreabilidade canônico | [`../traceability/living-architecture-map.json`](../traceability/living-architecture-map.json) | Workflows, artifacts, contratos, dashboards e PRs recentes. |
| Schema registry | [`../schema-registry.json`](../schema-registry.json) | Registro central de schemas com gates de validação. |

## Quando usar cada artefato

```text
Novo incremento / PR     → ENGINEERING_PLAYBOOKS → Agent Increment Gate
Novo teste / gate CI     → TESTING_PLAYBOOK → Trilha D (quando qualidade)
Decisão arquitetural     → ADR_INDEX → criar ADR em docs/adr/
Quebra silenciosa        → CONTRACT_CATALOG → validar schema/contrato
Conflito entre branches  → LIVING_ARCHITECTURE_INDEX → boundaries/ownership
Troubleshooting CI/ops   → RUNTIME_EVIDENCE_GRAPH → timeline + artifacts
Onboarding agente/IA     → README (este) → living-architecture-index.json
```

## Impacto esperado

| Métrica | Ganho estimado |
| --- | --- |
| Velocidade de onboarding IA | +200% a +500% |
| Redução de conflitos de PR | -30% a -70% |
| Redução de retrabalho | -25% a -60% |
| Tempo de entendimento arquitetural | -50% a -80% |
| Throughput sustentável | +30% a +70% |

## Manutenção

Atualizar este hub quando houver:

- Novo módulo backend/frontend relevante.
- Novo workflow ou artifact operacional.
- Novo ADR transversal.
- Novo contrato/schema versionado.
- Novo playbook operacional.

Validação report-only: workflow [`Living Architecture Traceability`](../../.github/workflows/living-architecture-traceability.yml).

## Referências cruzadas

- [`docs/00_INDICE_CANONICO.md`](../00_INDICE_CANONICO.md) — índice canônico geral.
- [`docs/governanca/PADRAO_OURO_ENTERPRISE.md`](../governanca/PADRAO_OURO_ENTERPRISE.md) — baseline enterprise.
- [`docs/runbooks/living-architecture-traceability.md`](../runbooks/living-architecture-traceability.md) — runbook de rastreabilidade.
- [`AGENTS.md`](../../AGENTS.md) — guia operacional para agentes.
