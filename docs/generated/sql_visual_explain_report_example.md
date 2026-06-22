# Relatório SQL Visual Explain

## Query analisada

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

## Contexto

Consulta analisada para identificação de fontes, relacionamentos, filtros e ordenação.

## Missão

Transformar a consulta em leitura lógica reutilizável para documentação, revisão e governança.

## Análise

### Tabelas principais

- `users`

### Joins

- `orders ON o.user_id = u.id`

### Filtros

- `o.total > 100`

### Ordenação

- `o.total DESC`

## Resultado esperado

Documento inicial para revisão humana, versionamento e evolução para análise com SQLGlot/EXPLAIN ANALYZE.
