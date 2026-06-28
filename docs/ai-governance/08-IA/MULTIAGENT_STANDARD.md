# Multiagent Standard

Codigo: AI-GOV-IA-002

## Objetivo

Padronizar colaboracao entre agentes especializados.

## Documento canônico

A especificação completa está em [ARQUITETURA_MULTIAGENTE_ENTERPRISE.md](ARQUITETURA_MULTIAGENTE_ENTERPRISE.md), incluindo:

- 10 agentes especializados com prompts e handoffs
- Estratégia de orquestração em 4 camadas
- Contrato JSON padronizado (`agent-output.schema.json`)
- Regras de paralelismo seguro e validação cruzada

## Agentes recomendados

| Camada | Agentes |
| --- | --- |
| Estratégica | Arquiteto, Governança, Product Owner |
| Técnica | Backend, Frontend, DevOps, QA |
| Operacional | Operacional Autônomo |
| Corporativa | Power Platform, SQL/Analytics |

Catálogo completo: [agents/README.md](agents/README.md).

## Regras

- Cada agente deve possuir responsabilidade clara.
- Toda decisao deve ser rastreavel via `correlation_id`.
- Outputs devem seguir `docs/contracts/agent-output.schema.json`.
- Agentes nao devem publicar diretamente em producao sem validacao.
- Pipeline deve funcionar como gate obrigatorio.
- Execucao paralela permitida apenas em escopos/branch isolados.

## ReqSys

ReqSys utiliza orquestracao multiagente para backlog, analise tecnica, testes, arquitetura e documentacao viva. A automacao real fica em GitHub Actions + scripts + agentes por PR; chats fixos sao contexto, nao runtime autonomo.

## Referencias

- [AGENT_GOVERNANCE.md](AGENT_GOVERNANCE.md)
- [ARQUITETURA_MULTIAGENTE_ENTERPRISE.md](ARQUITETURA_MULTIAGENTE_ENTERPRISE.md)
- [coordenador-principal-menu-operacional.md](../../runbooks/coordenador-principal-menu-operacional.md)
