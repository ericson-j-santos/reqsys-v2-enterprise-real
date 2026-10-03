#!/usr/bin/env python3
"""
SQL Visual Explain Analyzer

Objetivo:
- Receber uma consulta SQL.
- Extrair uma análise lógica básica.
- Gerar Markdown e Mermaid para documentação versionada.

Observação:
- Usa apenas biblioteca padrão para não quebrar CI por dependência nova.
- Próximo incremento pode trocar o parser heurístico por SQLGlot.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SqlAnalysis:
    tables: list[str]
    joins: list[str]
    filters: list[str]
    order_by: list[str]


def normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.strip())


def analyze_sql(sql: str) -> SqlAnalysis:
    compact = normalize_sql(sql)

    tables = re.findall(r"\bFROM\s+([\w\.]+)(?:\s+\w+)?", compact, flags=re.IGNORECASE)
    joins = re.findall(r"\bJOIN\s+([\w\.]+)(?:\s+\w+)?\s+ON\s+(.+?)(?=\bJOIN\b|\bWHERE\b|\bGROUP\b|\bORDER\b|$)", compact, flags=re.IGNORECASE)
    where_match = re.search(r"\bWHERE\s+(.+?)(?=\bGROUP\b|\bORDER\b|$)", compact, flags=re.IGNORECASE)
    order_match = re.search(r"\bORDER\s+BY\s+(.+?)(?=$)", compact, flags=re.IGNORECASE)

    join_descriptions = [f"{table} ON {condition.strip()}" for table, condition in joins]
    filters = [where_match.group(1).strip()] if where_match else []
    order_by = [order_match.group(1).strip().rstrip(';')] if order_match else []

    return SqlAnalysis(tables=tables, joins=join_descriptions, filters=filters, order_by=order_by)


def render_markdown(sql: str, analysis: SqlAnalysis) -> str:
    tables = "\n".join(f"- `{item}`" for item in analysis.tables) or "- Não identificado"
    joins = "\n".join(f"- `{item}`" for item in analysis.joins) or "- Não identificado"
    filters = "\n".join(f"- `{item}`" for item in analysis.filters) or "- Não identificado"
    order_by = "\n".join(f"- `{item}`" for item in analysis.order_by) or "- Não identificado"

    return f"""# Relatório SQL Visual Explain

## Query analisada

```sql
{sql.strip()}
```

## Contexto

Consulta analisada para identificação de fontes, relacionamentos, filtros e ordenação.

## Missão

Transformar a consulta em leitura lógica reutilizável para documentação, revisão e governança.

## Análise

### Tabelas principais

{tables}

### Joins

{joins}

### Filtros

{filters}

### Ordenação

{order_by}

## Resultado esperado

Documento inicial para revisão humana, versionamento e evolução para análise com SQLGlot/EXPLAIN ANALYZE.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera relatório Markdown de análise SQL visual.")
    parser.add_argument("--sql", help="SQL em texto.")
    parser.add_argument("--input", help="Arquivo .sql de entrada.")
    parser.add_argument("--output", default="sql_visual_explain_report.md", help="Arquivo Markdown de saída.")
    args = parser.parse_args()

    if not args.sql and not args.input:
        parser.error("Informe --sql ou --input")

    sql = args.sql if args.sql else Path(args.input).read_text(encoding="utf-8")
    analysis = analyze_sql(sql)
    report = render_markdown(sql, analysis)
    Path(args.output).write_text(report, encoding="utf-8")
    print(f"Relatório gerado: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
