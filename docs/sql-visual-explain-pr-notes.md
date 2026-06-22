# Notas para PR — SQL Visual Explain Stack

## Resumo

Este PR aplica as duas recomendações práticas solicitadas para análise visual e governada de SQL.

## Principais entregas

- Documentação operacional.
- ADR.
- Runbook.
- Lab HTML.
- Script Python inicial.
- Teste unitário.
- Exemplos SQL.
- Diagramas Mermaid/ERD.

## Validação esperada no PR

```bash
python -m pytest tests/test_sql_visual_explain_analyzer.py -v
```

## Observação

SQLGlot não foi adicionado neste PR para manter a mudança menor, com menor risco de CI. O roadmap já está versionado.
