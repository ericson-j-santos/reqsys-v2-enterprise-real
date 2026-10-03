# Plano de CI — SQL Visual Explain Stack

## Objetivo

Validar automaticamente o incremento sem introduzir dependências externas no pipeline.

## Comandos recomendados

```bash
python -m pytest tests/test_sql_visual_explain_analyzer.py -v
python scripts/sql_visual_explain_analyzer.py \
  --input examples/sql/orders_users_example.sql \
  --output docs/generated/sql_visual_explain_report_local.md
```

## Critérios de aceite

- Teste unitário aprovado.
- Script executado sem erro.
- Relatório gerado em Markdown.
- Nenhum segredo ou dado sensível nos arquivos de exemplo.

## Próximo incremento de CI

Adicionar workflow específico para SQL Visual Explain quando a estrutura final do pipeline estiver estabilizada.
