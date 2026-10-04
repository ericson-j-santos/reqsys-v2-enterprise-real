#!/usr/bin/env python3
"""Gerador offline de documentação para consultas SQL.

Este utilitário é deliberadamente estático:
- não abre conexão com banco;
- não executa SQL;
- não executa EXPLAIN/EXPLAIN ANALYZE;
- gera apenas análise heurística, Markdown e Mermaid.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

DESTRUCTIVE_PATTERN = re.compile(
    r"\b(delete|update|insert|drop|truncate|alter|create|grant|revoke)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class SqlAnalysis:
    tables: list[str]
    joins: list[str]
    filters: list[str]
    order_by: list[str]
    destructive_commands: list[str]


def normalize_sql(sql: str) -> str:
    without_line_comments = re.sub(r"--.*$", "", str(sql or ""), flags=re.MULTILINE)
    without_block_comments = re.sub(r"/\*[\s\S]*?\*/", "", without_line_comments)
    return re.sub(r"\s+", " ", without_block_comments.strip())


def analyze_sql(sql: str) -> SqlAnalysis:
    compact = normalize_sql(sql)

    tables = re.findall(r"\bFROM\s+([\w\.]+)(?:\s+\w+)?", compact, flags=re.IGNORECASE)
    joins = re.findall(
        r"\bJOIN\s+([\w\.]+)(?:\s+\w+)?\s+ON\s+(.+?)(?=\bJOIN\b|\bWHERE\b|\bGROUP\b|\bORDER\b|$)",
        compact,
        flags=re.IGNORECASE,
    )
    where_match = re.search(
        r"\bWHERE\s+(.+?)(?=\bGROUP\b|\bORDER\b|$)",
        compact,
        flags=re.IGNORECASE,
    )
    order_match = re.search(r"\bORDER\s+BY\s+(.+?)(?=$)", compact, flags=re.IGNORECASE)

    join_descriptions = [f"{table} ON {condition.strip()}" for table, condition in joins]
    filters = [where_match.group(1).strip()] if where_match else []
    order_by = [order_match.group(1).strip().rstrip(";")] if order_match else []
    destructive_commands = sorted({match.group(1).upper() for match in DESTRUCTIVE_PATTERN.finditer(compact)})

    return SqlAnalysis(
        tables=tables,
        joins=join_descriptions,
        filters=filters,
        order_by=order_by,
        destructive_commands=destructive_commands,
    )


def render_mermaid(analysis: SqlAnalysis) -> str:
    nodes: list[str] = []
    edges: list[str] = []
    seen: set[str] = set()

    def node_id(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9_]", "_", name)

    for table in analysis.tables:
        identifier = node_id(table)
        if identifier not in seen:
            nodes.append(f'  {identifier}["{table}"]')
            seen.add(identifier)

    for join in analysis.joins:
        table = join.split(" ON ", 1)[0]
        identifier = node_id(table)
        if identifier not in seen:
            nodes.append(f'  {identifier}["{table}"]')
            seen.add(identifier)
        if analysis.tables:
            edges.append(f"  {node_id(analysis.tables[0])} --> {identifier}")

    body = "\n".join([*nodes, *edges]) or '  empty["Nenhuma tabela identificada"]'
    return f"flowchart LR\n{body}"


def render_markdown(sql: str, analysis: SqlAnalysis) -> str:
    tables = "\n".join(f"- `{item}`" for item in analysis.tables) or "- Não identificado"
    joins = "\n".join(f"- `{item}`" for item in analysis.joins) or "- Não identificado"
    filters = "\n".join(f"- `{item}`" for item in analysis.filters) or "- Não identificado"
    order_by = "\n".join(f"- `{item}`" for item in analysis.order_by) or "- Não identificado"
    destructive = (
        "\n".join(f"- `{item}`" for item in analysis.destructive_commands)
        if analysis.destructive_commands
        else "- Nenhum comando potencialmente destrutivo identificado."
    )
    mermaid = render_mermaid(analysis)

    return f"""# Relatório SQL Visual Explain

> Análise estática/offline. Este relatório **não executa SQL nem EXPLAIN ANALYZE** e não é evidência de performance do banco.

## Query analisada

```sql
{sql.strip()}
```

## Tabelas principais

{tables}

## Joins

{joins}

## Filtros

{filters}

## Ordenação

{order_by}

## Segurança

{destructive}

## Fluxo lógico

```mermaid
{mermaid}
```

## Próximo passo seguro

Use o Query Intelligence do ReqSys para análise interativa. EXPLAIN/EXPLAIN ANALYZE deve ser executado somente em ambiente controlado, por ferramenta de banco apropriada e com revisão humana.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera documentação estática de uma consulta SQL.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--sql", help="SQL em texto.")
    source.add_argument("--input", help="Arquivo .sql de entrada.")
    parser.add_argument("--output", default="sql_visual_explain_report.md", help="Arquivo Markdown de saída.")
    args = parser.parse_args()

    sql = args.sql if args.sql is not None else Path(args.input).read_text(encoding="utf-8")
    report = render_markdown(sql, analyze_sql(sql))
    Path(args.output).write_text(report, encoding="utf-8")
    print(f"Relatório estático gerado: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
