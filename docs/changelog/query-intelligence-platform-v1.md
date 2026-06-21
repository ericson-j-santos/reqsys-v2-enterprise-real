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

### CI/CD

- Adicionado `tee` no job `Backend Tests + Coverage (pytest)` para capturar a saída integral do pytest em `/tmp/backend-pytest-output.log`.
- Adicionado relatório JUnit em `/tmp/backend-pytest-junit.xml`.
- Adicionado relatório de cobertura XML em `/tmp/backend-coverage.xml`.
- Adicionado artifact `backend-pytest-coverage-report` publicado com `if: always()` para permitir diagnóstico completo mesmo quando o coverage gate falhar.

### Pendências controladas

- Aguardar nova execução do CI após commit de diagnóstico.
- Baixar artifact `backend-pytest-coverage-report` se o backend pytest continuar falhando.
- Corrigir teste específico ou cobertura mínima a partir do relatório completo.
- Integrar histórico persistente em incremento posterior.
- Integrar EXPLAIN seguro apenas após adapter governado.
