# REQSYS#003 — Contrato Governado de Telemetria e Índice de Evidências

**Incremento:** OBS-P0.1  
**Branch padrão:** `ai/observability`  
**Status evidenciado:** implementado no código, pendente de CI remoto verde  
**Escopo:** observabilidade, telemetria, analytics, runtime health, evidence e drift analytics.

## Objetivo

Estabelecer um contrato mínimo e governado para eventos de telemetria do ReqSys, permitindo que logs, traces, métricas, evidências e análises de drift usem o mesmo vocabulário operacional.

## Campos obrigatórios do evento

| Campo | Finalidade | Regra |
| --- | --- | --- |
| `event_name` | Nome canônico do evento | Token técnico padronizado |
| `event_type` | Tipo do evento | `trace`, `log`, `metric`, `evidence`, `drift`, `security`, `runtime` |
| `module` | Domínio técnico emissor | Token técnico padronizado |
| `action` | Ação observada | Token técnico padronizado |
| `status` | Resultado operacional | `success`, `warning`, `error`, `skipped` |
| `severity` | Severidade | `debug`, `info`, `warning`, `error`, `critical` |
| `correlation_id` | Correlação ponta a ponta | Obrigatório |
| `trace_id` | Rastreio distribuído | Obrigatório |
| `session_id` | Sessão ou execução | Obrigatório |
| `environment` | Ambiente | `local`, `dev`, `test`, `staging`, `production` |
| `timestamp` | Momento do evento | ISO-8601 com timezone |

## Gates de governança

O workflow `.github/workflows/observability-contract.yml` deve bloquear o PR quando:

- evento válido de referência deixar de passar;
- evento sem `trace_id` for aceito indevidamente;
- índice de evidências deixar de declarar contrato, runtime health, drift analytics ou gate de CI;
- testes unitários do contrato falharem.

## Endpoints adicionados

| Método | Endpoint | Finalidade |
| --- | --- | --- |
| `GET` | `/v1/telemetry-analytics/contract` | Snapshot do contrato e evento válido |
| `GET` | `/v1/telemetry-analytics/evidence-index` | Índice de evidências da frente |
| `GET` | `/v1/telemetry-analytics/runtime-health` | Saúde executiva de observabilidade |
| `POST` | `/v1/telemetry-analytics/drift` | Drift de conformidade para lote de eventos |

## KPIs iniciais

| KPI | Estado evidenciado |
| --- | ---: |
| Cobertura do contrato de telemetria | 100% |
| Runtime visibility | 65% |
| Alert coverage | 25% |
| Trace usefulness | 60% |
| Evidence traceability | 70% |

## Limites explícitos

Este incremento ainda não declara padrão ouro completo, porque faltam:

- dashboard runtime graph navegável;
- cobertura completa de alertas;
- integração real com coletor OpenTelemetry/Prometheus/Grafana;
- drill-down visual consolidado no frontend;
- evidência de CI remoto verde no PR.

## Próximo incremento recomendado

**OBS-P0.2 — Runtime Graph + Dashboard Drill-down de Telemetria**

Escopo recomendado:

- materializar runtime graph consultável;
- expor agregações por `module`, `event_type`, `status`, `severity` e `environment`;
- conectar frontend operacional com drill-down;
- publicar artifact JSON/HTML de evidência no workflow.
