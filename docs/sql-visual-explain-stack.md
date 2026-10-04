# SQL Visual Explain Stack

## Objetivo

Complementar a **Query Intelligence Platform** já integrada ao ReqSys com um fluxo offline para documentação, ensino e revisão de consultas SQL.

A superfície interativa canônica permanece `/query-intelligence`. O utilitário Python deste incremento gera documentação estática e **não conecta em banco nem executa SQL**.

## Camadas

| Camada | Superfície | Papel |
|---|---|---|
| Interativa | `/query-intelligence` | análise estática, riscos e relações lógicas |
| Offline | `scripts/sql_visual_explain_analyzer.py` | relatório Markdown/Mermaid versionável |
| Exemplo | `examples/sql/orders_users_example.sql` | massa sem dados reais |
| Lab | `public/sql-visual-explain-lab.html` | explicação visual estática |
| Banco | DBeaver/pgAdmin/DataGrip ou equivalente | execução e plano real, fora do analisador |

## Limites

- O analisador não executa SQL.
- Não abre conexão de banco.
- Não mede custo do otimizador.
- Não executa `EXPLAIN ANALYZE`.
- O parser é heurístico; não substitui parser AST completo.
- Comandos potencialmente destrutivos são sinalizados na saída.

## Fluxo seguro

1. analisar a intenção em Query Intelligence;
2. gerar relatório offline quando for necessário versionar evidência documental;
3. revisar a consulta;
4. executar `EXPLAIN` em ambiente controlado;
5. executar `EXPLAIN ANALYZE` apenas quando a operação for segura e autorizada;
6. nunca usar o lab ou o relatório estático como prova de performance real.

## Exemplo

```bash
python scripts/sql_visual_explain_analyzer.py \
  --input examples/sql/orders_users_example.sql \
  --output /tmp/sql_visual_explain_report.md
```
