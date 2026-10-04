# ADR-020 — Análise inteligente de consultas SQL

## Decisão

O ReqSys passa a oferecer uma análise estática de SQL na aplicação, sem conexão com banco e sem execução da consulta.

A funcionalidade extrai colunas, tabelas, aliases, junções, filtros, agregações, ordenação e CTEs; gera relações lógicas e alertas de risco; e sinaliza indícios de dados pessoais apenas a partir dos nomes das colunas.

## Segurança

- SQL é tratado como entrada não confiável.
- Nenhum comando é executado.
- Comandos de alteração são classificados como risco.
- Não há acesso a credenciais ou conexão com banco.
- A análise é local no navegador.

## Integração

- rota protegida: `/query-intelligence`;
- serviço: `frontend/src/services/queryIntelligence.js`;
- tela: `frontend/src/views/QueryIntelligenceView.vue`;
- teste unitário: `frontend/src/services/queryIntelligence.test.js`;
- validação ponta a ponta: `frontend/tests/e2e/query-intelligence.spec.js`;
- a rota também integra o catálogo canônico de responsividade.
