# ADR-035 — Trilha E: Arquitetura Viva

## Status

Aceito incrementalmente em 2026-06-27.

## Contexto

O ReqSys já possui documentação de arquitetura, ADRs, diagramas em `docs/arquitetura/`, runtime topology no backend (`build_runtime_topology`) e rastreabilidade em `living-architecture-map.json`. Faltava consolidar essas peças em uma trilha navegável, versionada e validável como **architecture-as-code**, sem alterar runtime ou deploy.

## Decisão

Criar a **Trilha E — Arquitetura Viva** como pacote aditivo em `docs/architecture/trilha-e/` com seis capacidades:

| Capacidade | Artefato canônico |
|---|---|
| Diagramas vivos | `diagrams.json` (Mermaid versionado) + viewer legado |
| ADRs | Índice em `inventory.json` apontando para `docs/adr/` |
| Runtime topology | `runtime-topology.json` alinhado a `build_runtime_topology` |
| Fluxo navegável | `fluxo-navegavel.json` + hub HTML |
| Inventory | `inventory.json` (serviços, APIs, workflows, dashboards) |
| Architecture-as-code | `architecture-as-code.json` + schema + gerador |

Validação report-only via workflow `trilha-e-arquitetura-viva.yml` e script `scripts/trilha_e_arquitetura_viva.py`.

## Regras de governança

| Tema | Decisão |
|---|---|
| Conflito | Apenas arquivos novos ou extensões aditivas ao mapa de rastreabilidade. |
| Runtime | Nenhuma alteração obrigatória em endpoints existentes. |
| Modo | `report_only` — problemas viram pendências, não bloqueiam CI principal. |
| Diagramas | Fonte canônica em JSON; viewer legado permanece compatível. |
| ADRs | Novas decisões transversais continuam em `docs/adr/`. |
| Evidência | Relatório em `audit/trilha-e/trilha-e-arquitetura-viva-report.json`. |

## Consequências

### Benefícios

- Arquitetura viva navegável, auditável e versionada junto ao código.
- Inventário machine-readable de componentes e decisões.
- Alinhamento explícito entre topology estática e runtime API.
- Base para expansão futura (drill-down na SPA, geração automática de ADR index).

### Limitações

- Topology estática não substitui snapshot runtime ao vivo.
- Hub HTML é estático; integração profunda com `MonitoramentoOperacionalView` fica para incremento futuro.
- ADR index é curado manualmente no `inventory.json` (gerador valida existência dos paths).

## Rollback

Reverter:

- `docs/architecture/trilha-e/`
- `docs/adr/ADR-035-trilha-e-arquitetura-viva.md`
- `docs/runbooks/trilha-e-arquitetura-viva.md`
- `docs/contracts/trilha-e-arquitetura-viva.schema.json`
- `scripts/trilha_e_arquitetura_viva.py`
- `.github/workflows/trilha-e-arquitetura-viva.yml`
- Entradas adicionadas em `docs/traceability/living-architecture-map.json`

## Referências

- `docs/ai-governance/01-ARQUITETURA/LIVING_ARCHITECTURE.md`
- `docs/governanca/PADRAO_OURO_ENTERPRISE.md` (seção Arquitetura viva)
- `docs/architecture/runtime-correlation-graph.md`
- `docs/runbooks/living-architecture-traceability.md`
