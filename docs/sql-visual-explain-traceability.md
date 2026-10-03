# Rastreabilidade — SQL Visual Explain Stack

## Origem

Solicitação: aplicar recomendações práticas para uso de ferramentas equivalentes ao actuallyEXPLAIN e consultas derivadas.

## Requisito funcional

| ID | Requisito | Evidência |
|---|---|---|
| RF-SQL-001 | Documentar fluxo didático | `docs/sql-visual-explain-stack.md` |
| RF-SQL-002 | Documentar fluxo enterprise | `docs/sql-visual-explain-stack.md` |
| RF-SQL-003 | Criar consultas derivadas | `docs/sql-visual-explain-queries.md` |
| RF-SQL-004 | Criar artefato visual | `public/sql-visual-explain-lab.html` |
| RF-SQL-005 | Criar analisador inicial | `scripts/sql_visual_explain_analyzer.py` |
| RF-SQL-006 | Criar teste mínimo | `tests/test_sql_visual_explain_analyzer.py` |

## Requisito não funcional

| ID | Requisito | Evidência |
|---|---|---|
| RNF-SQL-001 | Sem dependência externa no primeiro incremento | Script usa biblioteca padrão |
| RNF-SQL-002 | Documentação versionada | Arquivos em `docs/` |
| RNF-SQL-003 | Guard rails de produção | `docs/sql-visual-explain-production-guards.md` |
| RNF-SQL-004 | Maturidade evidenciada | `docs/sql-visual-explain-status.md` |
