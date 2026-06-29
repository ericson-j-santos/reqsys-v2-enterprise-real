# Índice Canônico — ReqSys

Data de referência: 2026-06-27

Este índice consolida os documentos canônicos do ReqSys para orientar humanos, agentes, automações e futuras evoluções do repositório.

## Hub Padrão Ouro Tier 1 (máximo ROI documentação viva)

| Documento | Finalidade |
| --- | --- |
| [`docs/padrao-ouro/README.md`](padrao-ouro/README.md) | Hub central — infraestrutura de documentação operacional viva. |
| [`docs/padrao-ouro/LIVING_ARCHITECTURE_INDEX.md`](padrao-ouro/LIVING_ARCHITECTURE_INDEX.md) | Mapa navegável de módulos, fluxos, ownership e dashboards. |
| [`docs/padrao-ouro/ADR_INDEX.md`](padrao-ouro/ADR_INDEX.md) | Catálogo de decisões arquiteturais. |
| [`docs/padrao-ouro/RUNTIME_EVIDENCE_GRAPH.md`](padrao-ouro/RUNTIME_EVIDENCE_GRAPH.md) | Grafo workflows → PRs → artifacts → métricas → dashboards. |
| [`docs/padrao-ouro/CONTRACT_CATALOG.md`](padrao-ouro/CONTRACT_CATALOG.md) | Inventário de schemas, eventos, APIs e contratos. |
| [`docs/padrao-ouro/ENGINEERING_PLAYBOOKS.md`](padrao-ouro/ENGINEERING_PLAYBOOKS.md) | Fluxos operacionais para incrementos, CI, merge e evidências. |
| [`docs/padrao-ouro/TESTING_PLAYBOOK.md`](padrao-ouro/TESTING_PLAYBOOK.md) | Pirâmide, árvores, gates e convenções da camada de testes. |
| [`docs/padrao-ouro/living-architecture-index.json`](padrao-ouro/living-architecture-index.json) | Índice machine-readable para agentes/IA. |

## Documentos obrigatórios

| Documento | Finalidade |
| --- | --- |
| `docs/01_REQSYS_REFERENCIA_CONSOLIDADA.md` | Referência executiva, técnica e operacional do ReqSys. |
| `docs/adr/ADR-0001-arquitetura-padrao-ouro.md` | Decisão de arquitetura padrão ouro. |
| `docs/adr/ADR-0002-seguranca-gates-producao.md` | Gates mínimos de segurança e bloqueio de produção. |
| `docs/adr/ADR-0003-ambientes-dev-hml-prod.md` | Separação e governança de ambientes. |
| `docs/adr/ADR-0004-ci-cd-qualidade.md` | CI/CD, testes, quality gates e política de merge. |
| `docs/adr/ADR-0005-observabilidade-auditoria.md` | Observabilidade, logs, auditoria e correlação. |
| `docs/adr/ADR-0006-analytics-drilldown-schema-driven-ui.md` | Analíticos, drill-down e UI orientada a schema. |
| `docs/adr/ADR-0021-coderabbit-fast-review-governance.md` | Governança de revisão IA/CodeRabbit com fast path, PRs pequenos e deep review condicional. |
| `docs/governance/CODERABBIT_FAST_REVIEW_GUARDRAILS.md` | Guardrails operacionais para reduzir tempo de CodeRabbit sem reduzir governança. |
| `docs/ci/CI_ACCELERATION_STRATEGY.md` | Estratégia de aceleração de CI, fast path e validações profundas condicionais. |
| `docs/devops/PLANO_EVOLUTIVO_DEVOPS_CORPORATIVO.md` | Plano estratégico para evolução DevOps corporativa, Platform Engineering, DevSecOps, observabilidade e IA operacional. |
| `docs/strategy/REQSYS_ATUALIZACAO_CONSOLIDADA_2026-06-26.md` | Atualização estratégica consolidada de 26/06/2026, com foco em runtime operacional, observabilidade, ambientes e operação autônoma. |
| `docs/runbooks/coordenador-principal-menu-operacional.md` | Menu operacional do Coordenador Principal: ordem de leitura de artifacts, semáforo, workflows allowlisted e fluxo por incremento. |
| `docs/runbooks/coordenador-status-consolidator.md` | Consolidador automático dos artifacts 1–2 em `coordenador-status.json`. |

## Regra de precedência

1. Segurança, LGPD, auditoria e gates de produção prevalecem sobre produtividade.
2. CI Fast determinístico é o primeiro gate operacional para PRs pequenos.
3. CI completo e verde é pré-condição para merge em `main` quando requerido por proteção, risco ou política do repositório.
4. Revisão IA/CodeRabbit complementa qualidade, mas não substitui testes, SAST, validação de workflow ou revisão humana obrigatória.
5. Documentação canônica deve refletir o estado real do código.
6. Dúvidas devem ser registradas como pendência, não assumidas como fato.

## Fluxo canônico

```text
visão estratégica → engenharia de requisitos → processos → arquitetura → ADRs → backlog → roadmap → qualidade → DevOps → observabilidade → riscos → documentação → produção
```

## Fluxo operacional de PR

```text
micro PR → CI Fast → revisão objetiva → merge controlado → deep review condicional/pós-merge
```

## Política de atualização

Atualizar este índice sempre que houver novo documento canônico, ADR relevante, decisão técnica transversal ou mudança no fluxo operacional do ReqSys.

## Runbooks e operação

- [REQSYS#002.P5 — Runbook de execução real e rollback operacional Fly.io](FLYIO_PUBLIC_RUNTIME_RUNBOOK.md)
