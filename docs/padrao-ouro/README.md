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


## Foco operacional atual

Para manter o Padrão Ouro em modo de consolidação, priorize apenas incrementos que reforcem rastreabilidade, evidência e redução de risco operacional antes de abrir novas frentes.

| Prioridade | Direção prática | Evidência esperada |
| --- | --- | --- |
| 1 | Consolidar CI, gates e artifacts já existentes. | Workflow verde ou artifact versionado referenciado no grafo. |
| 2 | Fechar gaps documentados de arquitetura, contratos ou testes. | ADR, contrato, playbook ou teste atualizado com referência cruzada. |
| 3 | Evitar novas superfícies funcionais sem `Agent Increment Gate` permitido. | Saída do gate anexada ao PR ou registrada como pendência. |

Critério de pronto: qualquer mudança sob este hub deve deixar claro **qual artefato Tier 1 foi fortalecido**, **qual evidência valida o ganho** e **qual risco operacional foi reduzido**.

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
