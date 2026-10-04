# Query Intelligence Platform

## Objetivo

Fornecer análise estática e explicável de consultas SQL no frontend sem executar o SQL informado e sem acessar dados reais.

## Requisitos

1. A rota `/query-intelligence` deve permanecer registrada no router, navegação e catálogo responsivo.
2. A análise deve ser local/estática e não pode executar a consulta informada.
3. SQL deve ser tratado como entrada não confiável.
4. Comandos destrutivos como `DROP`, `DELETE`, `UPDATE` e `TRUNCATE` devem gerar achado de segurança segundo as regras do analisador.
5. Inferência de PII deve usar apenas nomes/identificadores presentes na consulta e não pode afirmar inspeção de dados reais.
6. A tela deve permanecer utilizável em viewport responsivo e sem overflow horizontal.
7. Fontes, espaçamento e densidade de UI devem usar os design tokens governados.
8. A funcionalidade não altera banco, não executa SQL e não promove ambiente.

## Critérios de aceite

- `frontend/src/services/queryIntelligence.test.js` fica verde no HEAD atual.
- `frontend/tests/e2e/query-intelligence.spec.js` valida abertura da rota e o fluxo de análise sem execução.
- A rota `/query-intelligence` está presente em `frontend/src/router/index.js`, `navCatalog.js` e `rotasResponsivas.js`.
- Um SQL destrutivo conhecido produz achado de segurança no analisador.
- Um SQL somente leitura é analisado sem qualquer chamada de execução de banco.
- O gate de design tokens aprova `QueryIntelligenceView.vue`.
- O Pre-PR Readiness aprova o HEAD exato com `behind_by=0`.
- CI principal, CI Enterprise Fast, CI E2E Governado e demais gates obrigatórios ficam verdes no mesmo SHA.
