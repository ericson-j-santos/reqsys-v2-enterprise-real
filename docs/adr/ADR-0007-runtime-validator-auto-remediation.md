# ADR-0007 — Runtime Validator & Auto-Remediation Engine

## Status
Aceita.

## Contexto
O ReqSys Enterprise precisa de uma camada operacional autônoma, auditável e governada por evidências para validar saúde em runtime, workflows de CI/CD, estabilidade, incidentes e remediações controladas.

## Decisão
Criar o módulo `Runtime Validator` no backend FastAPI com APIs REST versionadas por domínio operacional em `/api/runtime-validator/*`, serviços tipados por Pydantic e dashboard Vue/Vuetify dedicado. A primeira entrega usa armazenamento em memória para timeline curta e contratos explícitos para futura persistência em SQL Server/PostgreSQL e cache Redis.

## Consequências
- Toda resposta operacional propaga `correlation_id`.
- Remediações iniciam em `dry_run` e ações perigosas possuem circuit breaker.
- Evidências, eventos de governança e rollback seguro fazem parte do contrato de resposta.
- A persistência durável deve ser adicionada em migração posterior sem quebrar o contrato REST.
