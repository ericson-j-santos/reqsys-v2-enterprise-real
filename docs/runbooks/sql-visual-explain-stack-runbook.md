# Runbook — SQL Visual Explain Stack

## Gerar relatório offline

```bash
python scripts/sql_visual_explain_analyzer.py \
  --input examples/sql/orders_users_example.sql \
  --output /tmp/sql_visual_explain_report.md
```

## Validar

```bash
python -m pytest tests/test_sql_visual_explain_analyzer.py -v
```

## Uso com banco

1. Use Query Intelligence/relatório offline para leitura lógica.
2. Revise a consulta e identifique comandos destrutivos.
3. Em ambiente controlado, use a ferramenta SQL aprovada para `EXPLAIN`.
4. Só execute `EXPLAIN ANALYZE` se a consulta for segura para execução real.
5. Não rode consultas mutáveis/destrutivas para produzir plano em produção sem autorização específica.

## Falha do parser heurístico

Se a consulta usar sintaxe complexa não reconhecida:

- não inferir resultado inexistente;
- documentar o limite;
- validar com parser/ferramenta apropriada;
- considerar SQLGlot em incremento próprio.
