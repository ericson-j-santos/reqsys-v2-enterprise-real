# Padrão Ouro — Infraestrutura de Documentação Viva (Tier 1)

Data de referência: 2026-06-29

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
| 7 | **Foco Padrão Ouro** | [`FOCO_PADRAO_OURO.md`](FOCO_PADRAO_OURO.md) | Sequência prioritária para consolidar qualidade, rastreabilidade e prontidão de merge com diff mínimo. |

## Foco operacional Padrão Ouro

Plano detalhado em [`FOCO_PADRAO_OURO.md`](FOCO_PADRAO_OURO.md). Para manter o ciclo em **máximo ROI**, qualquer atuação neste repositório deve priorizar a menor mudança capaz de fortalecer uma das frentes abaixo:

| Prioridade | Frente | Evidência mínima | Critério de pronto |
| --- | --- | --- | --- |
| P0 | Governança de incremento | Agent Increment Gate, status do coordenador ou justificativa explícita de escopo fechado | Sem nova frente bloqueada, duplicada ou sem dono. |
| P1 | Rastreabilidade viva | Atualização em índice, contrato, ADR, runbook ou grafo de evidência | Humanos e agentes conseguem localizar owner, workflow, artifact e rollback. |
| P2 | CI e qualidade sustentável | Teste, lint, schema validation ou workflow report-only aplicável | Falha reproduzível vira evidência; sucesso vira artifact rastreável. |
| P3 | Segurança operacional | Gates de produção, segredos, CORS, JWT, auditoria ou correlation ID revisados quando tocados | Nenhum segredo, PII ou relaxamento produtivo entra no PR. |
| P4 | Documentação acionável | Playbook/runbook curto com comando validado ou pendência explícita | O próximo agente sabe o próximo passo sem depender de contexto de chat. |

### Modo consolidação (`state_yellow`)

Enquanto o coordenador estiver em `state_yellow`, priorize estabilização e rastreabilidade sem abrir nova frente concorrente:

| # | Direção | Evidência esperada |
| --- | --- | --- |
| 1 | Consolidar CI, gates e artifacts já existentes. | Workflow verde ou artifact versionado referenciado no grafo. |
| 2 | Fechar gaps documentados de arquitetura, contratos ou testes. | ADR, contrato, playbook ou teste atualizado com referência cruzada. |
| 3 | Evitar novas superfícies funcionais sem `Agent Increment Gate` permitido. | Saída do gate anexada ao PR ou registrada como pendência. |

Checklist rápido antes de abrir/atualizar PR:

1. Confirmar o artefato Tier 1 afetado na tabela acima.
2. Registrar evidência programática possível, mesmo que report-only.
3. Declarar fora de escopo para evitar PR amplo.
4. Preferir atualização machine-readable quando a mudança alterar ownership, workflow, contrato ou módulo.
5. Manter rollback simples: reverter commit ou remover artifact sem impactar runtime.

Critério de saída: uma mudança Padrão Ouro só é pronta quando a evidência de gate, os artefatos Tier 1 afetados e o comando de validação focado estiverem rastreáveis no PR.


### Consolidador operacional Padrão Ouro

Para transformar o modo `state_yellow` em uma fila objetiva de estabilização, use o consolidador local antes de abrir ou atualizar PRs de consolidação:

```bash
python scripts/padrao_ouro_operational_consolidator.py --status-json artifacts/coordenador-status/coordenador-status.json
```

O relatório JSON gerado em `artifacts/padrao-ouro-operational-consolidator/` classifica a prontidão como:

| Readiness | Significado | Próximo incremento sugerido |
| --- | --- | --- |
| `gold` | Coordenador verde, Tier 1 completo e nova frente liberada. | `new_front` com gate explícito. |
| `consolidating` | Estado seguro para fechar evidências/CI sem abrir superfície nova. | `consolidate`. |
| `blocked` | Falta coordenador, ciclo operacional, Tier 1 ou há falha crítica. | `gap_fix` ou `consolidate`, conforme blockers. |

Use esse output como evidência objetiva no PR quando a demanda for “consolidar operacional padrão ouro”.

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
Foco Padrão Ouro      → FOCO_PADRAO_OURO → prioridades P0–P4
Novo incremento / PR     → ENGINEERING_PLAYBOOKS → Agent Increment Gate
Novo teste / gate CI     → TESTING_PLAYBOOK → Trilha D (quando qualidade)
Decisão arquitetural     → ADR_INDEX → criar ADR em docs/adr/
Quebra silenciosa        → CONTRACT_CATALOG → validar schema/contrato
Conflito entre branches  → LIVING_ARCHITECTURE_INDEX → boundaries/ownership
Troubleshooting CI/ops   → RUNTIME_EVIDENCE_GRAPH → timeline + artifacts
Onboarding agente/IA     → README (este) → living-architecture-index.json
```


## Protocolo rápido para agentes

Use este protocolo quando o pedido for amplo (ex.: "foco padrão ouro") ou quando houver dúvida entre criar frente nova, corrigir gap ou consolidar evidência.

| Prioridade | Fazer | Evidência mínima | Antiobjetivo |
| --- | --- | --- | --- |
| 1 | Localizar o domínio no Living Architecture Index e confirmar ownership antes de editar. | Link para módulo/owner ou trecho do índice usado. | Alterar arquivos fora do boundary sem justificativa. |
| 2 | Preferir correção de gap, consolidação ou documentação operacional antes de criar novo módulo. | `agent_increment_gate` com tipo adequado ou justificativa de indisponibilidade do artifact local. | Criar frente paralela sem gate. |
| 3 | Executar a menor validação reproduzível para o escopo tocado. | Comando local, exit code e limitação ambiental quando houver. | Declarar CI verde sem evidência. |
| 4 | Atualizar contratos, ADRs, runbooks ou matriz de testes quando a mudança afetar operação. | Arquivo de documentação atualizado junto do diff funcional. | Deixar conhecimento apenas no PR/chat. |
| 5 | Encerrar com commit convencional, PR com escopo/fora de escopo/riscos/rollback e próximos gates. | Commit + corpo de PR rastreável. | Misturar mudanças não relacionadas. |

```text
1. Ler este README + living-architecture-index.json.
2. Classificar o pedido: gap_fix, consolidate, hotfix, close_duplicate ou new_front.
3. Rodar agent_increment_gate com o tipo classificado quando o artifact/status estiver disponível.
4. Aplicar diff mínimo e manter rastreabilidade em docs/padrao-ouro ou runbooks.
5. Validar o menor conjunto de comandos compatível com o escopo.
6. Commitar e abrir PR com evidência objetiva.
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
- Mudança de prioridade operacional no foco Padrão Ouro.

Validação report-only: workflow [`Living Architecture Traceability`](../../.github/workflows/living-architecture-traceability.yml).

## Referências cruzadas

- [`docs/00_INDICE_CANONICO.md`](../00_INDICE_CANONICO.md) — índice canônico geral.
- [`docs/governanca/PADRAO_OURO_ENTERPRISE.md`](../governanca/PADRAO_OURO_ENTERPRISE.md) — baseline enterprise.
- [`docs/runbooks/living-architecture-traceability.md`](../runbooks/living-architecture-traceability.md) — runbook de rastreabilidade.
- [`AGENTS.md`](../../AGENTS.md) — guia operacional para agentes.
