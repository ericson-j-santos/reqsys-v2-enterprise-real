# ADR-022 — Codex Local Online integrado ao ReqSys

## Status

Proposto para validação em PR.

## Contexto

O pacote inicial era local, baseado em Ollama e Continue. A nova decisão operacional exige uma experiência online, validável por CI e preparada para integração com ReqSys sem expor credenciais no navegador.

## Decisão

Criar uma aplicação estática publicável no GitHub Pages, com modo demonstração seguro e suporte a endpoint backend configurável. O frontend não armazena credenciais e não executa modelo diretamente. A integração real deve ocorrer por backend governado.

## Consequências

- A aplicação fica acessível online após deploy do GitHub Pages.
- O uso real com LLM depende de backend seguro.
- O modo demonstração permite validação visual e operacional sem custo.
- A rastreabilidade é preservada por `correlation_id` e payload ReqSys.

## Guard rails

- Sem credencial no frontend.
- Bloqueio básico de conteúdo com indício de credencial ou PII.
- Publicação somente via workflow versionado.
- Evidência registrada no GitHub Actions.
