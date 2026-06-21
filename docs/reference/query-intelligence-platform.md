# Query Intelligence Platform

## Objetivo

A **Query Intelligence Platform** transforma consultas SQL em uma visão explicável, navegável e governada, permitindo que analistas, desenvolvedores, arquitetos e stakeholders compreendam intenção lógica, riscos, dependências e oportunidades de melhoria.

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

## Tipos de achados

| Tipo | Exemplos |
|---|---|
| Performance | `SELECT *`, ausência de filtro |
| Governança | campos com possível PII, SQL destrutivo |
| Manutenibilidade | múltiplas CTEs |
| Arquitetura | joins complexos, funções de janela |

## Pipeline lógico

```text
SQL
 ↓
Normalização segura
 ↓
Parser heurístico
 ↓
Modelo semântico
 ↓
Risk Engine
 ↓
Logical Graph
 ↓
UI navegável
 ↓
Explicação e governança
```

## Contrato de saída

```json
{
  "summary": "consulta dados de users, orders, relaciona 1 junção(ões), aplica filtros de negócio, ordena a saída.",
  "riskScore": 0,
  "riskLevel": "low",
  "tables": [
    { "table": "users", "alias": "u" },
    { "table": "orders", "alias": "o" }
  ],
  "joins": [
    { "type": "JOIN", "table": "orders", "alias": "o", "condition": "o.user_id = u.id" }
  ],
  "filters": "o.total > 100",
  "orderBy": "o.total DESC",
  "findings": [],
  "graph": {
    "nodes": [],
    "edges": []
  }
}
```

## Regras de segurança

- O módulo não executa SQL.
- SQL informado deve ser tratado como entrada não confiável.
- Logs não devem conter SQL bruto quando houver risco de PII.
- Resultados devem registrar `correlation_id` quando integrados ao backend.
- Produção deve bloquear execução destrutiva futura sem feature flag e autorização explícita.

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
