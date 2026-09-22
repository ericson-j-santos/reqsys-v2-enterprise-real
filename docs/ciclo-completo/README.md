# ReqSys — Painel de Acompanhamento do Ciclo Completo

## Objetivo

Centralizar o acompanhamento operacional do ReqSys em uma visão única e versionável.

O painel cobre demanda, triagem, planejamento, implementação, CI, review, merge, evidência, deploy, validação pública e operação.

## Artefatos

| Arquivo | Finalidade |
|---|---|
| `docs/painel-ciclo-completo-reqsys.html` | Painel visual autocontido, sem CDN, pronto para abrir no navegador. |
| `docs/ciclo-completo/estado-ciclo-reqsys.json` | Fonte de dados estruturada para versionamento e automação futura. |
| `docs/ciclo-completo/ADR-REQSYS-CYCLE-TRACKER.md` | Decisão arquitetural do painel. |
| `docs/ciclo-completo/RUNBOOK_VERSIONAMENTO.md` | Passo a passo de versionamento e validação. |
| `docs/ciclo-completo/TEST_REPORT.md` | Evidência de validação estática. |
| `scripts/validar_painel_ciclo.py` | Validador local/CI do painel. |
| `.github/workflows/validar-painel-ciclo.yml` | Workflow dedicado para validar e publicar artifact. |

## Decisão operacional atual

Encerrar PR #18 e PR #20 como concluídos. Priorizar o PR #19: atualizar contra `main`, reexecutar CI completo e decidir merge se todos os checks permanecerem verdes.

## Issue canônica

- `#21 — REQ#021 - Versionar painel de acompanhamento do ciclo completo`

## Validação local

```bash
python scripts/validar_painel_ciclo.py
```

Resultado esperado:

```text
OK: painel de ciclo validado com sucesso
```

## Próxima evolução recomendada

Automatizar a atualização do JSON por GitHub Actions, coletando PRs, runs de CI, artifacts de validação pública e status de deploy.
