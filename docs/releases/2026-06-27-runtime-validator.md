# Release note — Runtime Validator & Auto-Remediation Engine

## Incluído
- Módulo backend com health, workflow validation, incident detection, remediation, timeline e dashboard payload.
- Dashboard operacional Vue/Vuetify em `/runtime-validator`.
- Testes automatizados de contrato REST.
- ADR e runbook operacional.
- Workflow CI dedicado para validação do runtime validator.

## Fora de escopo
- Persistência durável em SQL Server/PostgreSQL.
- Execução real de rollback ou rerun GitHub Actions.
- Integração Redis Streams em produção.
