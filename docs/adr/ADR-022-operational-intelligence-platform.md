# ADR-022 — Operational Intelligence Platform

## Status

Consolidado na arquitetura atual do ReqSys.

## Contexto

O PR #74 nasceu para reduzir gaps de telemetria distribuída, inteligência de runtime, observabilidade viva, resiliência e operação autônoma assistida.

A branch histórica ficou milhares de commits atrás da `main`. Desde então, o núcleo funcional foi extraído e evoluído por incrementos posteriores, incluindo a Operational Runtime Governance Platform.

## Decisão

Manter como capacidades canônicas do ReqSys:

- `correlation_id` ponta a ponta;
- telemetria estruturada;
- modelos de inteligência operacional;
- diagnóstico determinístico de runtime;
- recomendação governada de ação;
- endpoints `/monitoramento-operacional/runtime/health` e `/monitoramento-operacional/runtime/diagnostico`;
- integração do router no bootstrap FastAPI;
- testes críticos executáveis no backend;
- monitoramento operacional unificado na tela canônica atual.

## Superfícies atuais

| Capacidade | Superfície |
|---|---|
| Correlação | `backend/app/core/correlation.py` |
| Telemetria | `backend/app/core/telemetry.py` |
| Modelos | `backend/app/models/operational_intelligence_models.py` |
| Diagnóstico | `backend/app/services/runtime_intelligence_service.py` |
| Ação assistida | `backend/app/services/autonomous_operation_service.py` |
| API | `backend/app/api/operational_intelligence.py` |
| Bootstrap | `backend/app/main.py` |
| Testes | `backend/tests/test_operational_intelligence_critical_paths.py` |
| UI operacional | `frontend/src/views/MonitoramentoOperacionalView.vue` |

## Itens históricos não restaurados

- `backend/app/services/resilience_service.py`: retry genérico antigo; a arquitetura atual usa remediação/execução governada e não deve ganhar segundo executor paralelo.
- `backend/sql/002_operational_intelligence_platform.sql`: DDL SQL Server cru incompatível com a estratégia atual de modelos/migrações do backend.
- `.github/workflows/operational-intelligence-governance.yml`: workflow redundante frente aos gates canônicos de governança, segurança, SDD e CI.
- `frontend/src/views/RuntimeCenterView.vue`: substituído pela tela canônica `MonitoramentoOperacionalView.vue`, mais completa e integrada.
- alterações históricas em layout/router: a navegação atual deve ser preservada, sem restaurar estruturas de junho.

## Regras de governança

1. Estado operacional não pode ser promovido sem evidência atual.
2. Diagnóstico deve ser determinístico e limitado a score de 0 a 100.
3. Estado degradado/bloqueado deve exigir intervenção/aprovação apropriada.
4. Nenhum retry genérico deve contornar política de remediação atual.
5. Nenhum workflow novo deve duplicar um gate já canônico.
6. Evidência de SHA anterior não autoriza merge ou promoção.

## Consequência

O objetivo do #74 é preservado sem reintroduzir arquitetura paralela ou artefatos obsoletos.
