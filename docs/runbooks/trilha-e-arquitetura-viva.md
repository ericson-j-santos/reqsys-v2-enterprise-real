# Runbook — Trilha E: Arquitetura Viva

**Data:** 2026-06-27  
**Modo:** report-only  
**ADR:** [`docs/adr/ADR-035-trilha-e-arquitetura-viva.md`](../adr/ADR-035-trilha-e-arquitetura-viva.md)

## Objetivo

Operar a trilha de arquitetura viva com diagramas versionados, ADRs indexados, runtime topology, fluxo navegável, inventário e architecture-as-code — sem alterar deploy ou runtime.

## Artefatos canônicos

| Item | Caminho |
|---|---|
| Architecture-as-Code | [`docs/architecture/trilha-e/architecture-as-code.json`](../architecture/trilha-e/architecture-as-code.json) |
| Inventory | [`docs/architecture/trilha-e/inventory.json`](../architecture/trilha-e/inventory.json) |
| Runtime Topology | [`docs/architecture/trilha-e/runtime-topology.json`](../architecture/trilha-e/runtime-topology.json) |
| Diagramas vivos | [`docs/architecture/trilha-e/diagrams.json`](../architecture/trilha-e/diagrams.json) |
| Fluxo navegável | [`docs/architecture/trilha-e/fluxo-navegavel.json`](../architecture/trilha-e/fluxo-navegavel.json) |
| Hub HTML | [`docs/architecture/trilha-e/index.html`](../architecture/trilha-e/index.html) |
| Schema | [`docs/contracts/trilha-e-arquitetura-viva.schema.json`](../contracts/trilha-e-arquitetura-viva.schema.json) |
| Gerador | [`scripts/trilha_e_arquitetura_viva.py`](../../scripts/trilha_e_arquitetura_viva.py) |
| Workflow | [`.github/workflows/trilha-e-arquitetura-viva.yml`](../../.github/workflows/trilha-e-arquitetura-viva.yml) |

## Navegação rápida

1. Abrir o **hub HTML** para visão integrada.
2. Consultar **inventory** para serviços, APIs, workflows e ADRs.
3. Explorar **diagrams.json** (Mermaid) ou o viewer legado em `docs/arquitetura/`.
4. Comparar **runtime-topology.json** com `/api/runtime/dashboard` (seção `runtime-topology-preview`).
5. Seguir **fluxo-navegavel.json** para drill-down entre capacidades.

## Validação local

```bash
python scripts/trilha_e_arquitetura_viva.py
cat audit/trilha-e/trilha-e-arquitetura-viva-report.json
```

## Validação em CI

O workflow **Trilha E — Arquitetura Viva** executa em:

- `workflow_dispatch`
- `push`/`pull_request` quando arquivos da trilha mudam

Publica artifact `trilha-e-arquitetura-viva-${{ github.run_id }}` com relatório em `audit/trilha-e/`.

## Critérios de manutenção

| Evento | Ação |
|---|---|
| Novo ADR transversal | Adicionar entrada em `inventory.json` → `adrs` |
| Novo serviço ou módulo API relevante | Atualizar `inventory.json` |
| Mudança de topology runtime | Alinhar `runtime-topology.json` e validar contra `build_runtime_topology` |
| Novo diagrama | Adicionar em `diagrams.json` e link no hub |
| Nova capacidade na trilha | Atualizar `architecture-as-code.json` e `fluxo-navegavel.json` |

## Integração com arquitetura viva existente

- Mapa de rastreabilidade: [`docs/traceability/living-architecture-map.json`](../traceability/living-architecture-map.json)
- Workflow irmão: [Living Architecture Traceability](../../.github/workflows/living-architecture-traceability.yml)
- Correlation graph: [`docs/architecture/runtime-correlation-graph.md`](../architecture/runtime-correlation-graph.md)

## O que não fazer

- Não tratar o hub estático como substituto do runtime dashboard ao vivo.
- Não bloquear merge por warnings do modo report-only.
- Não commitar segredos ou credenciais reais nos diagramas ou inventory.
