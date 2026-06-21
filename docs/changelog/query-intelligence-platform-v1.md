# Changelog — Query Intelligence Platform v1

## 2026-06-21

### Adicionado

- Serviço frontend `queryIntelligence.js` com análise estática de SQL.
- View operacional `QueryIntelligenceView.vue`.
- Rota protegida `/query-intelligence`.
- Entrada no menu lateral do ReqSys.
- Testes unitários para normalização, extração de colunas, joins, filtros, riscos e PII.
- ADR-020.
- Referência canônica do módulo.

### Segurança

- O incremento inicial não executa SQL.
- Comandos destrutivos são tratados como achado de segurança.
- PII é inferida apenas por padrões de nomes de colunas.

### Pendências controladas

- Validar `npm run test:unit` em runner ou ambiente local.
- Rebase/atualização da branch, pois o comparativo indicou divergência em relação à `main`.
- Integrar histórico persistente em incremento posterior.
- Integrar EXPLAIN seguro apenas após adapter governado.
