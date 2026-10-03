# Estratégia de Testes — SQL Visual Explain Stack

## Testes atuais

| Teste | Cobertura |
|---|---|
| `test_analyze_sql_extracts_core_parts` | Tabela, join, filtro e ordenação |

## Testes futuros

| Cenário | Prioridade |
|---|---:|
| SELECT simples | P0 |
| JOIN múltiplo | P0 |
| WHERE com AND/OR | P0 |
| GROUP BY | P1 |
| HAVING | P1 |
| CTE | P1 |
| Subquery | P1 |
| Window function | P2 |
| Dialetos diferentes | P2 |

## Critério

Antes de declarar maturidade enterprise, o parser deve cobrir no mínimo SELECT, JOIN, WHERE, GROUP BY, CTE e subquery com SQLGlot.
