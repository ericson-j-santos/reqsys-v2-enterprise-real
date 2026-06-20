# Índice Canônico — ReqSys

Data de referência: 2026-06-20

Este índice consolida os documentos canônicos do ReqSys para orientar humanos, agentes, automações e futuras evoluções do repositório.

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

## Regra de precedência

1. Segurança, LGPD, auditoria e gates de produção prevalecem sobre produtividade.
2. CI completo e verde é pré-condição para merge em `main`.
3. Documentação canônica deve refletir o estado real do código.
4. Dúvidas devem ser registradas como pendência, não assumidas como fato.

## Fluxo canônico

```text
visão estratégica → engenharia de requisitos → processos → arquitetura → ADRs → backlog → roadmap → qualidade → DevOps → observabilidade → riscos → documentação → produção
```

## Política de atualização

Atualizar este índice sempre que houver novo documento canônico, ADR relevante, decisão técnica transversal ou mudança no fluxo operacional do ReqSys.
