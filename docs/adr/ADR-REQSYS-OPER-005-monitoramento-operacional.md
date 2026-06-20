# ADR — REQSYS-OPER-005 — Monitoramento Operacional ReqSys

## Status

Proposto.

## Contexto

O ReqSys precisa exibir, de forma rastreável e auditável, sinais mínimos de operação relacionados a PRs, CI/CD, gates, validações públicas e integrações críticas.

A frente REQSYS-OPER-004 consolidou a governança documental. A frente REQSYS-OPER-005 inicia a implementação do endpoint e da tela `/monitoramento-operacional`.

## Decisão

Implementar um endpoint backend próprio, `/monitoramento-operacional`, retornando um snapshot canônico com envelope padrão da API.

Implementar uma tela frontend inicial, também em `/monitoramento-operacional`, com cards, tabela analítica e filtros por query string.

## Consequências positivas

- Centraliza sinais operacionais no ReqSys.
- Cria base para drill-down e analytics.
- Permite evolução incremental para GitHub Actions, PRs, gates reais e histórico persistido.
- Mantém separação entre monitoramento e decisão de merge/deploy.

## Consequências negativas

- A primeira versão ainda usa snapshot mínimo interno.
- A coleta real de GitHub Actions e PRs precisará de integração segura posterior.
- Será necessário definir política de retenção para histórico operacional.

## Regras obrigatórias

- Não expor credenciais, secrets, tokens ou dados pessoais no frontend.
- CI verde é condição necessária, mas não suficiente.
- Estado `bloqueado` prevalece sobre demais estados.
- PR em draft ou incremento em andamento não deve aparecer como pronto para merge.
- Toda coleta deve carregar identificador de correlação.

Refs #46
