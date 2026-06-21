# Query Intelligence Platform

## Objetivo

A **Query Intelligence Platform** transforma consultas SQL em uma visão explicável, navegável e governada, permitindo compreender intenção lógica, riscos, dependências e oportunidades de melhoria.

## Rota operacional

```text
/query-intelligence
```

## Capacidades iniciais

| Capacidade | Descrição |
|---|---|
| Análise estática | Inspeciona SQL sem executar comandos |
| Intenção lógica | Resume o objetivo provável da consulta |
| Grafo lógico | Converte SQL em nós e relações navegáveis |
| Risk scoring | Calcula risco técnico e governança |
| Achados | Lista pontos de atenção com severidade |
| Governança | Detecta padrões inseguros ou frágeis |

## Pipeline lógico

```text
SQL → Normalização segura → Parser heurístico → Modelo semântico → Risk Engine → Logical Graph → UI navegável
```

## Regras de segurança

- O módulo não executa SQL.
- SQL informado é entrada não confiável.
- Logs não devem conter SQL bruto quando houver risco de PII.
- Comandos destrutivos são achados de segurança.
- EXPLAIN runtime só deve entrar em incremento futuro com adapter governado.

## Exemplo recomendado

```sql
SELECT
    u.id,
    u.name,
    o.total
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE o.total > 100
ORDER BY o.total DESC;
```

## Roadmap

| Incremento | Entrega |
|---|---|
| 1 | Análise estática + UI |
| 2 | Histórico e versionamento |
| 3 | Policies configuráveis |
| 4 | EXPLAIN seguro por adapter |
| 5 | OpenTelemetry + lineage |
| 6 | IA explicável governada |
