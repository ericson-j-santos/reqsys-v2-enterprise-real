# Exemplos SQL

Este diretório contém consultas de exemplo para análise, documentação viva e testes operacionais.

## Arquivos

| Arquivo | Finalidade |
|---|---|
| `orders_users_example.sql` | Consulta base `users` + `orders` e consultas derivadas |

## Uso

```bash
python scripts/sql_visual_explain_analyzer.py \
  --input examples/sql/orders_users_example.sql \
  --output docs/generated/sql_visual_explain_report_local.md
```
