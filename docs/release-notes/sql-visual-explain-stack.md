# Release Note — SQL Visual Explain Stack

## Tipo

Incremento documental e operacional.

## Itens adicionados

- Documento operacional `docs/sql-visual-explain-stack.md`.
- ADR `docs/adr/ADR-SQL-VISUAL-EXPLAIN-STACK.md`.
- Runbook `docs/runbooks/sql-visual-explain-stack-runbook.md`.
- Lab visual HTML `public/sql-visual-explain-lab.html`.
- Script inicial `scripts/sql_visual_explain_analyzer.py`.
- Teste unitário `tests/test_sql_visual_explain_analyzer.py`.
- Exemplo SQL `examples/sql/orders_users_example.sql`.

## Valor entregue

- Aplica o fluxo didático actuallyEXPLAIN + IA + DBeaver/pgAdmin.
- Aplica a base enterprise DBeaver/DataGrip + EXPLAIN ANALYZE + SQLGlot futuro + Mermaid/ERD versionado.
- Introduz automação inicial sem dependência externa para reduzir risco no CI.

## Próximo incremento

- Adicionar SQLGlot como dependência controlada.
- Gerar AST real.
- Gerar Mermaid automaticamente.
- Integrar relatório ao pipeline e à UI operacional do ReqSys.
