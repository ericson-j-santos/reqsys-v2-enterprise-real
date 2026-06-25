# Operational Analytics Persistence v1.1

## Objetivo

Transformar observabilidade runtime em analytics temporal governado com armazenamento duravel.

## Endpoint

- `/api/runtime/analytics`

## Estado implementado

- storage duravel SQL via `DurableRuntimeAnalyticsStore`;
- uso do `DATABASE_URL` da aplicacao;
- tabela governada `runtime_operational_snapshots`;
- janela limitada por `max_snapshots`;
- failure rate;
- availability score;
- media e maximo de risk score;
- tendencia de risco, pendencias e bloqueios;
- sanitizacao por allowlist antes da persistencia;
- placeholders governados para MTTR e lead time.

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

- endpoint retorna `schema_version = 1.1.0`;
- `window.mode = durable_sql` no endpoint;
- `guardrails.durable_storage_enabled = true` no endpoint;
- storage duravel preserva snapshots entre instancias;
- campos fora da allowlist nao sao persistidos.

## Limitacoes conhecidas

Esta fatia persiste snapshots operacionais e prepara a base temporal. MTTR e lead time continuam como placeholders governados porque ainda dependem de eventos duraveis de ciclo de incidente e deploy.

## Proximo incremento

- modelo duravel de incidentes runtime;
- ciclo `opened -> acknowledged -> resolved`;
- calculo real de MTTR;
- integracao com deploy events para lead time;
- exposicao de drill-down analitico por periodo/status/risco.
