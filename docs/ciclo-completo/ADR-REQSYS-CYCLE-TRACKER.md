---
status: ReqSys / Plataforma Corporativa
date: 2026-06-22
deciders: Arquitetura / Engenharia
context: ReqSys / Plataforma Corporativa
version: 1.0.0
---

# ADR — REQSYS-CYCLE-TRACKER


## Status

Proposto.

## Contexto

O ciclo ReqSys envolve múltiplas frentes: GitHub PRs, CI, revisão, evidência, deploy, validação pública e operação. Sem uma visão única, as decisões ficam espalhadas em conversas, PRs, comentários e workflows.

## Decisão

Adotar um painel versionado de acompanhamento do ciclo completo, composto por:

1. HTML autocontido para consulta humana.
2. JSON estruturado como fonte de dados auditável.
3. Matriz de gates bloqueantes.
4. Mapa de PRs, checks, pendências e decisões.
5. Validação automatizável por script e GitHub Actions.

## Consequências positivas

- Maior rastreabilidade.
- Menor perda de contexto.
- Decisão de merge/deploy mais objetiva.
- Base futura para integração com Redmine, GitHub Actions, Power BI e RAG.

## Atenções

- A versão inicial é estática.
- A atualização automática deve mascarar dados sensíveis.
- Nenhum segredo deve ser gravado em JSON, log, artifact ou HTML.

## Gates mínimos preservados

- Produção bloqueada com auth desligada.
- CORS wildcard bloqueado.
- JWT exige issuer/audience.
- `JWT_EXP_MINUTES <= 0` bloqueado.
- Login demo bloqueado em produção.
- Logs não podem expor dados sensíveis.
- Auditoria deve ter `correlation_id`.
