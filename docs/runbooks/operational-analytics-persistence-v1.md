# Operational Analytics Persistence v1.2

## Objetivo

Transformar observabilidade runtime em analytics temporal governado com armazenamento duravel, ciclo de incidentes e MTTR real.

## Endpoint

- `/api/runtime/analytics`

## Estado implementado

- storage duravel SQL via `DurableRuntimeAnalyticsStore`;
- uso do `DATABASE_URL` da aplicacao;
- tabela governada `runtime_operational_snapshots`;
- tabela governada `runtime_incident_events`;
- janela limitada por `max_snapshots`;
- failure rate;
- availability score;
- media e maximo de risk score;
- tendencia de risco, pendencias e bloqueios;
- sanitizacao por allowlist antes da persistencia;
- ciclo `incident_opened -> incident_acknowledged -> incident_resolved`;
- calculo real de MTTR quando houver ao menos um incidente aberto e resolvido;
- placeholder governado para lead time.

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

## Regras de ciclo de incidente

| Status recebido | Ultimo evento | Evento gerado |
|---|---|---|
| `degraded`, `blocked`, `vermelho`, `bloqueado` | nenhum/resolvido | `incident_opened` |
| `degraded`, `blocked`, `vermelho`, `bloqueado` | `incident_opened` | `incident_acknowledged` |
| `healthy`, `ok`, `green`, `verde`, `attention` | aberto/reconhecido | `incident_resolved` |

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

- endpoint retorna `schema_version = 1.2.0`;
- `window.mode = durable_sql` no endpoint;
- `guardrails.durable_storage_enabled = true` no endpoint;
- `guardrails.incident_lifecycle_enabled = true` no endpoint;
- storage duravel preserva snapshots entre instancias;
- storage duravel preserva eventos de incidente entre instancias;
- ciclo de incidente gera `incident_opened`, `incident_acknowledged` e `incident_resolved`;
- MTTR retorna `calculated` quando houver ciclo resolvido;
- campos fora da allowlist nao sao persistidos.

## Limitacoes conhecidas

Esta fatia calcula MTTR por eventos runtime internos. Lead time continua como placeholder governado porque ainda depende de eventos duraveis de deploy.

## Proximo incremento

- integracao com deploy events para lead time;
- drill-down analitico por periodo/status/risco/incidente;
- endpoint dedicado para timeline de incidentes;
- UI operacional navegavel para incident lifecycle.
