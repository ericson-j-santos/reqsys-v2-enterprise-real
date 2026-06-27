# Completion Projection — Runbook

## Objetivo

Gerar e publicar artifact de projeção estatística de conclusão do ReqSys de forma governada e report-only.

## Execução local

```bash
python scripts/completion_projection_engine.py \
  --output artifacts/completion-projection/completion-projection.json \
  --repository reqsys \
  --run-id local \
  --event-name manual
```

## Workflow CI

Workflow: `.github/workflows/completion-projection.yml`

- Disparo: `schedule` (diário), `push` em `main` (paths do workflow) e `workflow_dispatch`
- Modo: `report_only`
- Artifact: `completion-projection-json`

## Consumo

| Consumidor | Uso |
|---|---|
| Backend `/v1/estatisticas/projecao-conclusao` | Lê artifact se presente; fallback para baseline |
| Frontend `/estatisticas` (aba Projeção) | Exibe snapshot com separação evidenciado/projeção |
| OCC / dashboards | Pode ingerir `completion-projection.json` |

## Interpretação

- **Padrão ouro consolidado (52%)** é evidenciado, não projeção.
- **Probabilidades finais** são estatísticas de cenário, não compromisso de entrega.
- **Cenário acelerado** assume CI auto-healing, branches independentes e validação contínua ativos.

## Rollback

Remover ou reverter artifact não afeta runtime. API volta ao baseline versionado no serviço.

## Referências

- `docs/statistics/COMPLETION_PROJECTION_SPEC.md`
- `docs/contracts/completion-projection.schema.json`
- `docs/adr/ADR-022-autonomous-operations-platform-p0-1.md`
