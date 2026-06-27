# Trilha E — Arquitetura Viva

Pacote aditivo de **architecture-as-code** para o ReqSys, consolidando seis capacidades sem alterar runtime ou deploy.

## Capacidades

| # | Capacidade | Artefato |
|---|------------|----------|
| 1 | Diagramas vivos | [`diagrams.json`](diagrams.json) |
| 2 | ADRs | [`inventory.json`](inventory.json) → `adrs` |
| 3 | Runtime topology | [`runtime-topology.json`](runtime-topology.json) |
| 4 | Fluxo navegável | [`fluxo-navegavel.json`](fluxo-navegavel.json) |
| 5 | Inventory | [`inventory.json`](inventory.json) |
| 6 | Architecture-as-code | [`architecture-as-code.json`](architecture-as-code.json) |

## Navegação

- **Hub HTML:** [`index.html`](index.html)
- **ADR:** [`docs/adr/ADR-035-trilha-e-arquitetura-viva.md`](../../adr/ADR-035-trilha-e-arquitetura-viva.md)
- **Runbook:** [`docs/runbooks/trilha-e-arquitetura-viva.md`](../../runbooks/trilha-e-arquitetura-viva.md)

## Validação

```bash
python scripts/trilha_e_arquitetura_viva.py
```

Workflow: `.github/workflows/trilha-e-arquitetura-viva.yml` (report-only).

## Compatibilidade

- Viewer legado de diagramas: `docs/arquitetura/index.html`
- Runtime API: `/api/runtime/dashboard` (seção `runtime-topology-preview`)
- Mapa de rastreabilidade: `docs/traceability/living-architecture-map.json`
