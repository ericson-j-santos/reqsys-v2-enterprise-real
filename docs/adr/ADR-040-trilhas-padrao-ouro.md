# ADR-040 — Trilhas A–E: Padrão Ouro Consolidado

## Status

Aceito em 2026-06-27.

## Contexto

As trilhas A–E foram implementadas incrementalmente (PRs #394–#398). Apenas a Trilha E possuía pacote completo de architecture-as-code. Faltava consolidador transversal que valide critérios padrão ouro comuns e hub navegável.

## Decisão

Criar pacote **Trilhas Padrão Ouro** com:

| Artefato | Caminho |
|---|---|
| Registry | `docs/architecture/trilhas/trilhas-registry.json` |
| Hub HTML | `docs/architecture/trilhas/index.html` |
| Consolidador | `scripts/trilhas_padrao_ouro.py` |
| Schema | `docs/contracts/trilhas-padrao-ouro.schema.json` |
| Workflow | `.github/workflows/trilhas-padrao-ouro.yml` |
| Runbook | `docs/runbooks/trilhas-padrao-ouro.md` |

Critérios padrão ouro por trilha: ADR, runbook, workflow, validator, schema, architecture-as-code, relatório e testes.

## Regras de governança

| Tema | Decisão |
|---|---|
| Modo | `report_only` — consolidador não bloqueia merge |
| Referência | Trilha E permanece modelo de arquitetura viva completa |
| Evolução | Novas trilhas exigem entrada no registry + validador |
| Integração | Registrar A–D em `living-architecture-map.json` |

## Consequências

### Benefícios

- Visão única de maturidade das cinco trilhas.
- Base para coordenador operacional e Runtime Health Center.

### Limitações

- Consolidador valida presença e relatórios; não executa probe Fly live nem E2E completo.

## Referências

- `docs/REQSYS_PADRAO_OURO_TRANSVERSAL.md`
- `docs/governanca/PADRAO_OURO_ENTERPRISE.md`
- `docs/adr/ADR-035-trilha-e-arquitetura-viva.md`
