# Catálogo de Consultas Derivadas — Users x Orders

## Consulta base

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

## Consultas derivadas

### Total gasto por usuário

```sql
SELECT
  u.id,
  u.name,
  SUM(o.total) AS total_gasto
FROM users u
JOIN orders o ON o.user_id = u.id
GROUP BY u.id, u.name
ORDER BY total_gasto DESC;
```

### Quantidade de pedidos por usuário

```sql
SELECT
  u.id,
  u.name,
  COUNT(o.id) AS quantidade_pedidos
FROM users u
JOIN orders o ON o.user_id = u.id
GROUP BY u.id, u.name
ORDER BY quantidade_pedidos DESC;
```

### Ticket médio por usuário

```sql
SELECT
  u.id,
  u.name,
  AVG(o.total) AS ticket_medio
FROM users u
JOIN orders o ON o.user_id = u.id
GROUP BY u.id, u.name
ORDER BY ticket_medio DESC;
```

### Usuários sem pedidos

```sql
SELECT
  u.id,
  u.name
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE o.id IS NULL;
```

### Pedidos acima da média geral

```sql
SELECT
  u.id,
  u.name,
  o.total
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE o.total > (
  SELECT AVG(total)
  FROM orders
)
ORDER BY o.total DESC;
```

### Ranking dos maiores pedidos por usuário

```sql
SELECT
  u.id,
  u.name,
  o.total,
  ROW_NUMBER() OVER (
    PARTITION BY u.id
    ORDER BY o.total DESC
  ) AS ranking_pedido
FROM users u
JOIN orders o ON o.user_id = u.id;
```

### Maior pedido de cada usuário

```sql
SELECT
  id,
  name,
  total
FROM (
  SELECT
    u.id,
    u.name,
    o.total,
    ROW_NUMBER() OVER (
      PARTITION BY u.id
      ORDER BY o.total DESC
    ) AS rn
  FROM users u
  JOIN orders o ON o.user_id = u.id
) x
WHERE rn = 1
ORDER BY total DESC;
```
