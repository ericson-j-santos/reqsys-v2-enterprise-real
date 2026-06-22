-- Exemplo base para SQL Visual Explain Stack

SELECT
  u.id,
  u.name,
  o.total
FROM users u
JOIN orders o ON o.user_id = u.id
WHERE o.total > 100
ORDER BY o.total DESC;

-- Total gasto por usuário
SELECT
  u.id,
  u.name,
  SUM(o.total) AS total_gasto
FROM users u
JOIN orders o ON o.user_id = u.id
GROUP BY u.id, u.name
ORDER BY total_gasto DESC;

-- Quantidade de pedidos por usuário
SELECT
  u.id,
  u.name,
  COUNT(o.id) AS quantidade_pedidos
FROM users u
JOIN orders o ON o.user_id = u.id
GROUP BY u.id, u.name
ORDER BY quantidade_pedidos DESC;

-- Ticket médio por usuário
SELECT
  u.id,
  u.name,
  AVG(o.total) AS ticket_medio
FROM users u
JOIN orders o ON o.user_id = u.id
GROUP BY u.id, u.name
ORDER BY ticket_medio DESC;
