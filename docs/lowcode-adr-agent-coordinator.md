# Coordenador ReqSys ADR via Hub Low-Code

Data: 2026-07-05  
Status: P0 governado  
Idioma: português do Brasil

## Objetivo

Disponibilizar, via API do Hub Low-Code, um agente **Coordenador ReqSys ADR** capaz de planejar a chamada dos agentes especializados conforme as ADRs canônicas do projeto.

A implementação é governada: por padrão, o coordenador não executa escrita externa. Ele retorna plano de roteamento, guardrails, rastreabilidade e critérios de aceite para execução posterior por pipeline autorizado, Power Automate, Copilot Studio ou outro runtime governado.

## Fonte de decisão

Base canônica:

- `docs/padrao-ouro/ADR_INDEX.md`

O índice define que o onboarding de agente/IA deve ler primeiro as ADRs fundacionais `ADR-0001` a `ADR-0006` e que decisões transversais exigem ADR registrada.

## Endpoints

### `GET /v1/hub-lowcode/agents/coordenador/adr-base`

Retorna o catálogo governado de ADRs, agentes, domínios, política de execução e rastreabilidade obrigatória.

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

## Comportamento esperado

A resposta contém:

- `correlation_id`
- objetivo
- coordenador
- roteamento por agente
- ADR base
- motivo de acionamento
- entrada esperada
- saída esperada
- modo `dry_run_plan` ou `ready_for_governed_dispatch`
- guardrails
- critérios de aceite

## Guardrails

1. Não executar escrita externa sem aprovação humana ou pipeline ALM autorizado.
2. Preservar `correlation_id` em chamadas, logs e evidências.
3. Não expor PII, tokens, chaves ou segredos em prompts, payloads ou logs.
4. Consultar ADRs fundacionais antes de decisões específicas com impacto transversal.
5. Registrar lacunas, riscos, trade-offs e evidência esperada por agente acionado.

## Próximo incremento recomendado

Integrar o resultado do endpoint `/agents/coordenador/planejar` ao Copilot Studio ou Power Automate para abrir tarefas governadas por agente, mantendo aprovação humana antes de qualquer escrita externa.
