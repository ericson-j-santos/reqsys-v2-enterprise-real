# Operational Analytics Persistence v1.3

## Objetivo

Transformar observabilidade runtime em analytics temporal governado com armazenamento duravel, ciclo de incidentes, MTTR real e lead time real por eventos de deploy.

## Endpoint

- `/api/runtime/analytics`

## Estado implementado

- storage duravel SQL via `DurableRuntimeAnalyticsStore`;
- uso do `DATABASE_URL` da aplicacao;
- tabela governada `runtime_operational_snapshots`;
- tabela governada `runtime_incident_events`;
- tabela governada `runtime_deploy_events`;
- janela limitada por `max_snapshots`;
- failure rate;
- availability score;
- media e maximo de risk score;
- tendencia de risco, pendencias e bloqueios;
- sanitizacao por allowlist antes da persistencia;
- ciclo `incident_opened -> incident_acknowledged -> incident_resolved`;
- calculo real de MTTR quando houver ao menos um incidente aberto e resolvido;
- ciclo `deploy_started -> deploy_finished`;
- calculo real de lead time quando houver ao menos um deploy iniciado e finalizado.

## Modelo duravel

Tabela: `runtime_operational_snapshots`

| Campo | Uso |
|---|---|
| `id` | chave tecnica incremental |
| `recorded_at` | data/hora UTC da captura |
| `correlation_id` | rastreabilidade operacional |
| `status` | status sintetico do runtime |
| `risk_score` | score operacional |
| `payload_json` | snapshot operacional sanitizado |

Tabela: `runtime_incident_events`

| Campo | Uso |
|---|---|
| `id` | chave tecnica incremental |
| `event_at` | data/hora UTC do evento |
| `incident_key` | chave operacional do incidente |
| `event_type` | `incident_opened`, `incident_acknowledged` ou `incident_resolved` |
| `status` | status runtime que gerou o evento |
| `correlation_id` | rastreabilidade operacional |
| `payload_json` | evento operacional sanitizado |

Tabela: `runtime_deploy_events`

| Campo | Uso |
|---|---|
| `id` | chave tecnica incremental |
| `event_at` | data/hora UTC do evento |
| `deploy_key` | chave operacional do deploy |
| `event_type` | `deploy_started` ou `deploy_finished` |
| `environment` | ambiente do deploy |
| `correlation_id` | rastreabilidade operacional |
| `payload_json` | evento de deploy sanitizado |

## Regras de ciclo de incidente

| Status recebido | Ultimo evento | Evento gerado |
|---|---|---|
| `degraded`, `blocked`, `vermelho`, `bloqueado` | nenhum/resolvido | `incident_opened` |
| `degraded`, `blocked`, `vermelho`, `bloqueado` | `incident_opened` | `incident_acknowledged` |
| `healthy`, `ok`, `green`, `verde`, `attention` | aberto/reconhecido | `incident_resolved` |

## Regras de ciclo de deploy

| Evento recebido | Evento normalizado |
|---|---|
| `deploy_started`, `deployment_started` | `deploy_started` |
| `deploy_finished`, `deployment_finished`, `deploy_succeeded`, `deployment_succeeded` | `deploy_finished` |

Os eventos de deploy podem ser informados no campo operacional `evidence.deploy_event` ou gravados diretamente pelo store interno.

## MTTR

O MTTR é calculado quando existe pelo menos um ciclo completo:

```text
incident_opened -> incident_resolved
```

O retorno `mttr` informa:

- `status`;
- `value_seconds`;
- `resolved_incidents`;
- `open_incidents`;
- `min_seconds`;
- `max_seconds`.

Quando não há incidente resolvido, o status retorna `insufficient_resolved_incidents`.

## Lead time

O lead time é calculado quando existe pelo menos um ciclo completo:

```text
deploy_started -> deploy_finished
```

O retorno `lead_time` informa:

- `status`;
- `value_seconds`;
- `finished_deploys`;
- `open_deploys`;
- `min_seconds`;
- `max_seconds`.

Quando não há deploy finalizado, o status retorna `insufficient_deploy_events`.

## Guardrails

- read-only no endpoint;
- sem secrets;
- sem PII;
- persistencia com allowlist de campos;
- sem acao destrutiva;
- sem alteracao de deploy;
- sem dependencia de servico externo.

## Campos permitidos no payload persistido

- `correlation_id`;
- `generated_at`;
- `status`;
- `risk_score`;
- `critical_counts`;
- `evidence`;
- `recorded_at`.

Campos fora da allowlist nao devem ser gravados, mesmo se aparecerem no snapshot de origem.

## Como validar

```bash
cd backend
pytest tests/test_runtime_analytics.py
```

Validacoes esperadas:

- endpoint retorna `schema_version = 1.3.0`;
- `window.mode = durable_sql` no endpoint;
- `guardrails.durable_storage_enabled = true` no endpoint;
- `guardrails.incident_lifecycle_enabled = true` no endpoint;
- `guardrails.deploy_lifecycle_enabled = true` no endpoint;
- storage duravel preserva snapshots entre instancias;
- storage duravel preserva eventos de incidente entre instancias;
- storage duravel preserva eventos de deploy entre instancias;
- ciclo de incidente gera `incident_opened`, `incident_acknowledged` e `incident_resolved`;
- MTTR retorna `calculated` quando houver ciclo resolvido;
- lead time retorna `calculated` quando houver ciclo de deploy finalizado;
- campos fora da allowlist nao sao persistidos.

## Limitacoes conhecidas

Esta fatia calcula lead time por eventos duraveis recebidos pelo runtime analytics. A captura automatica a partir de pipelines/deploy real ainda depende de integracao posterior com CI/CD.

## Proximo incremento

- integracao automatica com deploy events de GitHub Actions/GitLab CI;
- drill-down analitico por periodo/status/risco/incidente/deploy;
- endpoint dedicado para timeline operacional;
- UI operacional navegavel para incident lifecycle e deploy lifecycle.
