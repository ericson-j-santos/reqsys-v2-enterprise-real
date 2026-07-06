# Coordenador ReqSys ADR via Hub Low-Code

Data: 2026-07-05  
Status: implementado em API P0 governada  
Idioma: português do Brasil

## Objetivo

Disponibilizar, via API do Hub Low-Code, um agente **Coordenador ReqSys ADR** capaz de planejar a chamada dos agentes especializados conforme as ADRs canônicas do projeto.

A implementação é deliberadamente governada: por padrão, o coordenador **não executa escrita externa**. Ele retorna plano de roteamento, guardrails, rastreabilidade e critérios de aceite para execução posterior por pipeline autorizado, Power Automate, Copilot Studio ou outro runtime governado.

## Fonte de decisão

A base canônica consultada é o índice de ADRs em:

- `docs/padrao-ouro/ADR_INDEX.md`

O índice define que o onboarding de agente/IA deve ler primeiro as ADRs fundacionais `ADR-0001` a `ADR-0006` e que decisões transversais exigem ADR registrada.

## Endpoints

### `GET /v1/hub-lowcode/agents/coordenador/adr-base`

Retorna o catálogo governado de ADRs, agentes, domínios, critérios de acionamento e entregáveis esperados.

### `POST /v1/hub-lowcode/agents/coordenador/planejar`

Planeja o roteamento dos agentes conforme o objetivo informado.

Payload exemplo:

```json
{
  "objetivo": "Evoluir o ReqSys Low-Code com API, CI, segurança, observabilidade e UX operacional",
  "adr_refs": ["ADR-0001", "ADR-0002", "ADR-0004", "ADR-0005", "ADR-038"],
  "dry_run": true
}
```

Header recomendado:

```text
X-Correlation-Id: REQSYS-LOWCODE-ADR-COORD-001
```

## Agentes base

| ADR | Agente | Finalidade |
| --- | --- | --- |
| ADR-0001 | Arquiteto Enterprise | Arquitetura, modularização, contratos e impacto transversal |
| ADR-0002 | Agente de Segurança e Governança | JWT, CORS, PII/LGPD, secrets e gates produtivos |
| ADR-0003 | Agente DevOps de Ambientes | Dev/HML/Prod, drift e promoção |
| ADR-0004 | Agente DevOps/CI | Workflows, testes, quality gates e CI verde |
| ADR-0005 | Agente de Observabilidade | Logs, auditoria, métricas e correlation_id |
| ADR-0006 | Agente de Analytics e BI | Indicadores, drill-down e schema-driven UI |
| ADR-020 | Agente de Integrações Corporativas | APIs, conectores e permissões sob demanda |
| ADR-021 | Agente Frontend/UX | Experiência visual e retorno em tela |
| ADR-022 | Agente Operacional Autônomo Governado | Operação assistida e remediação controlada |
| ADR-023 | Agente Runtime Health | Healthcheck, remediação e validação pós-deploy |
| ADR-030 | Agente de Governança de PR | Automerge, branch policy e controle de mudanças |
| ADR-031 | Agente de Promoção e Risco Runtime | Go/no-go, risco runtime e rollback |
| ADR-032 | Agente de Dashboard Operacional | Semáforo, drill-down e evidência navegável |
| ADR-035 | Agente de Arquitetura Viva | Diagramas vivos, mapas e rastreabilidade |
| ADR-036 | Agente de Runtime Público | Fly.io, DuckDNS e readiness público |
| ADR-037 | Agente OpenTelemetry/Auditoria | Telemetria enterprise e correlação ponta a ponta |
| ADR-038 | Agente UX Operacional | UX operacional, estados e responsividade |
| ADR-039 | Agente QA/Governança Técnica | Testes, matriz de qualidade e evidências |
| ADR-040 | Agente Coordenador de Maturidade Padrão Ouro | Lacunas, Pareto e próximo incremento |
| ADR-041 | Agente de Secrets e Configuração Segura | Cofre local, criptografia e fallback seguro |
| ADR-USER-FINAL-SHELL | Agente de Produto e Usuário Final | Jornada final, usabilidade e clareza de produto |

## Guardrails

1. Não executar escrita externa sem aprovação humana ou pipeline ALM autorizado.
2. Preservar `correlation_id` em chamadas, logs e evidências.
3. Não expor PII, tokens, chaves ou segredos em prompts, payloads ou logs.
4. Consultar ADRs fundacionais antes de decisões específicas com impacto transversal.
5. Registrar lacunas, riscos, trade-offs e evidência esperada por agente acionado.

## Próximo incremento recomendado

Integrar o resultado do endpoint `/agents/coordenador/planejar` ao Copilot Studio ou Power Automate para abrir tarefas governadas por agente, mantendo aprovação humana antes de qualquer escrita externa.
