# Runbook — SQL Visual Explain Stack

## Objetivo

Padronizar o uso de ferramentas para análise, explicação, documentação e validação de consultas SQL.

## Execução local

### 1. Gerar relatório a partir de arquivo SQL

```bash
python scripts/sql_visual_explain_analyzer.py \
  --input examples/sql/orders_users_example.sql \
  --output sql_visual_explain_report.md
```

### 2. Gerar relatório a partir de texto SQL

```bash
python scripts/sql_visual_explain_analyzer.py \
  --sql "SELECT u.id, u.name, o.total FROM users u JOIN orders o ON o.user_id = u.id WHERE o.total > 100 ORDER BY o.total DESC;" \
  --output sql_visual_explain_report.md
```

### 3. Validar testes

```bash
python -m pytest tests/test_sql_visual_explain_analyzer.py -v
```

## Uso didático

1. Colar query no actuallyEXPLAIN.
2. Validar intenção lógica com IA.
3. Executar no DBeaver/pgAdmin.
4. Comparar resultado esperado com resultado real.

## Uso enterprise

1. Registrar query no repositório.
2. Gerar relatório Markdown.
3. Gerar diagrama Mermaid/ERD.
4. Executar `EXPLAIN` ou `EXPLAIN ANALYZE` em ambiente seguro.
5. Versionar evidências.

## Guard rails

- Não executar `EXPLAIN ANALYZE` destrutivo ou query pesada em produção sem aprovação.
- Não versionar dados sensíveis, tokens, connection strings ou PII.
- Não declarar status avançado sem evidência de teste ou CI.
- Não substituir revisão humana por explicação automática.
