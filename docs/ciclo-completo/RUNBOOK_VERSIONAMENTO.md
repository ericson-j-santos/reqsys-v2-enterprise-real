# Runbook — Versionar Painel de Ciclo Completo

## Issue canônica

- Issue: `#21`
- Título: `REQ#021 - Versionar painel de acompanhamento do ciclo completo`

## Branch

```bash
git checkout main
git pull origin main
git checkout -b feat/cycle-tracker-dashboard-20260618
```

## Arquivos versionados

```text
docs/painel-ciclo-completo-reqsys.html
docs/ciclo-completo/estado-ciclo-reqsys.json
docs/ciclo-completo/README.md
docs/ciclo-completo/ADR-REQSYS-CYCLE-TRACKER.md
docs/ciclo-completo/CHANGELOG.md
docs/ciclo-completo/TEST_REPORT.md
docs/ciclo-completo/RUNBOOK_VERSIONAMENTO.md
scripts/validar_painel_ciclo.py
.github/workflows/validar-painel-ciclo.yml
```

## Validação local

```bash
python scripts/validar_painel_ciclo.py
```

## PR recomendado

Base: `main`

Título:

```text
docs: add cycle tracker dashboard
```

Corpo mínimo:

```md
## Resumo

Adiciona painel de acompanhamento do ciclo completo do ReqSys, com HTML autocontido, JSON estruturado, ADR, README, changelog, relatório de validação e workflow de validação.

## Issue

Closes #21

## Testes

- `python scripts/validar_painel_ciclo.py`
- Workflow `Validar Painel de Ciclo ReqSys`

## Segurança

- Sem CDN externa.
- Sem secrets.
- Sem PII.
- Sem exposição de dados sensíveis.
```

## Pós-merge

1. Executar workflow `Validar Painel de Ciclo ReqSys`.
2. Executar workflow `Validação de Acessos Públicos — ReqSys`.
3. Atualizar o JSON com artifact real da validação pública.
4. Fechar issue #21 somente após PR mergeado e artifact arquivado.
