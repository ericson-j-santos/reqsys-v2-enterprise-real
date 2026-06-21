# ADR-2026-06-21 — CI Enterprise Continuous Maturity

## Status

Proposto para validação em PR.

## Contexto

Os pipelines do ReqSys vinham apresentando dois sintomas críticos:

1. tempo elevado até ficarem verdes;
2. regressões intermitentes mesmo após correções pontuais.

Esses sintomas indicam falhas estruturais típicas de esteiras sem determinismo suficiente: dependências instáveis, testes flaky, excesso de E2E bloqueante, falta de isolamento, ausência de observabilidade e ausência de política explícita para transformar falhas recorrentes em guardrails.

## Decisão

Adotar uma arquitetura de CI em camadas para maturidade enterprise contínua:

| Camada | Workflow | Bloqueia PR | Objetivo |
|---|---|---:|---|
| Guardrails determinísticos | `ci-enterprise-fast.yml` | Sim | Detectar instabilidade, insegurança e desvio de governança antes de testes caros |
| Backend fast | `ci-enterprise-fast.yml` | Sim | Ruff, unitários e build/testes rápidos |
| Frontend fast | `ci-enterprise-fast.yml` | Sim | Lint, typecheck, unitários e build |
| Full regression | `ci-enterprise-regression.yml` | Não por padrão | E2E completo, cobertura, segurança e regressão noturna/manual |
| Observabilidade | `ci-enterprise-observability.yml` | Indireto | Relatórios de maturidade, falhas recorrentes, flaky rate e tempo até verde |

## Regras canônicas

1. Todo PR deve passar pelo CI rápido.
2. Full regression deve rodar nightly, manualmente ou em release.
3. Falha recorrente não deve ser tratada apenas com rerun.
4. Cada falha recorrente deve gerar:
   - teste preventivo;
   - guardrail;
   - registro em documentação viva;
   - item de monitoramento operacional.
5. Produção deve continuar bloqueada por gates de segurança:
   - autenticação desligada;
   - CORS com `*`;
   - JWT sem validação real de issuer/audience/assinatura;
   - segredo literal versionado;
   - auditoria sem rastreabilidade.

## Consequências positivas

- Redução do tempo médio para feedback no PR.
- Menor custo de rerun.
- Separação entre validação rápida e regressão ampla.
- Maior previsibilidade de merge.
- Base para indicadores reais de maturidade.
- Menor chance de regressão silenciosa.

## Riscos

| Risco | Mitigação |
|---|---|
| Guardrails detectarem legado inseguro | Tratar achado como dívida técnica evidenciada, não mascarar status |
| Workflow novo conflitar com scripts existentes | Implementação defensiva: detecta frontend/backend antes de executar |
| E2E completo continuar lento | Rodar no workflow de regressão, não no fast path de PR |
| Status parecer avançado sem evidência | Diferenciar estado alvo de estado atual até CI verde e métricas coletadas |

## Critérios de aceite

- Branch com workflows novos criada.
- PR aberto em draft.
- CI fast executável.
- Regressão nightly/manual configurada.
- Observabilidade publica artifact Markdown.
- Guardrails geram relatório JSON e Markdown.
- Documentação viva atualizada.

## Decisão final

O ReqSys passa a tratar CI como plataforma governada, não como coleção de jobs isolados.
