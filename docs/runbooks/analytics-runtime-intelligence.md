# Runbook — Analytics Runtime Intelligence

## Snapshot

Endpoint canônico:

`GET /api/analytics-runtime-intelligence/snapshot`

Alias compatível:

`GET /v1/analytics-runtime-intelligence/snapshot`

## Interpretação

- `evidence_scope=repository_contract`: descreve implementação/versionamento, não runtime produtivo.
- `production_ready=false`: manter promoção bloqueada.
- `staging_ready=false`: faltam evidências externas completas.
- `runtime_sql_validation.production_evidence=false`: análise SQL é estática.

## Para elevar readiness

1. registrar URL externa do ambiente alvo;
2. capturar readback visual da execução atual;
3. executar smoke governado;
4. comprovar telemetria externa;
5. comprovar lineage da fonte real;
6. revalidar no mesmo SHA/runtime.

## Operational Sync

`tools/operational_sync/operational_sync_engine.py` aceita um arquivo JSON explícito de tarefas/evidências.

Sem input, o resultado correto é:

- `operational_evidence=false`;
- `status=evidence_required`.

Nunca preencher tarefas fixas com estado presumido de PR/CI.
