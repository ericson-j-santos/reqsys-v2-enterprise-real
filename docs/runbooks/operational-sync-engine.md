# Runbook — Operational Sync Engine v1

## Objetivo

Padronizar o monitoramento e a sincronização de tarefas, PRs, pipelines, agenda, Figma e relatórios HTML dentro do Runtime Operational Center do ReqSys.

## Execução local

```bash
python tools/operational-sync/operational_sync_engine.py --output artifacts/operational-sync-snapshot.json
```

## Execução CI

Workflow:

```text
.github/workflows/operational-sync-engine.yml
```

Gatilhos:

- pull request para `main`;
- push em `main`;
- execução manual;
- agenda útil: 08h, 12h e 18h BRT aproximado por cron UTC.

## Evidências esperadas

- `artifacts/operational-sync-snapshot.json` publicado como artifact.
- `correlation_id` presente no snapshot.
- score médio de risco.
- classificação de tarefas altas/críticas.
- lista de guard rails.

## Política de alerta

| Condição | Ação |
| --- | --- |
| CI verde em PR draft | manter monitoramento e liberar revisão quando autorizado |
| CI vermelho isolado | registrar risco e coletar job falho |
| CI vermelho recorrente | elevar prioridade para alta |
| produção impactada | bloquear automação e exigir aprovação humana |
| Figma indisponível | registrar fallback e manter HTML autocontido |

## Próxima ação operacional

1. Validar o novo run do workflow `Operational Sync Engine`.
2. Conferir artifact `operational-sync-snapshot`.
3. Atualizar o PR com link do artifact.
4. Corrigir PRs falhos antes de declarar maturidade consolidada.
