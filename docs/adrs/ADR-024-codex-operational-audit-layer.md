---
status: ReqSys / Plataforma Corporativa
date: 2026-06-22
deciders: Arquitetura / Engenharia
context: ReqSys / Plataforma Corporativa
version: 1.0.0
---

# ADR-024 — Codex Operational Audit Layer


## Status

Proposto para validacao em PR.

## Contexto

O backend governado do Codex Online ja executa analises autenticadas com rate limit e auditoria em log. Para operacao enterprise, a auditoria precisa ser persistente, consultavel e agregavel em dashboard operacional.

## Decisao

Adicionar uma camada operacional auditavel com:

- tabela `codex_auditoria`;
- persistencia por `correlation_id`;
- metricas de latencia, bloqueios, provider, publicacao ReqSys e score de confianca;
- endpoint `GET /v1/codex/operational-summary`;
- testes automatizados cobrindo persistencia e resumo operacional.

## Consequencias

- O Codex passa a ter base operacional propria.
- O dashboard do ReqSys pode consumir indicadores sem depender de logs brutos.
- A auditoria deixa de ser apenas observabilidade tecnica e vira ativo analitico.

## Guard rails

- Nao persistir prompts completos em log operacional.
- Persistir somente resumos truncados e fingerprint.
- Manter autenticação JWT para consultar indicadores.
- Preservar `correlation_id` como eixo de rastreabilidade.
