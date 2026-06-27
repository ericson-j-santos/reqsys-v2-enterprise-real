# Workflow Governance Consolidation

Atualizado em: 2026-06-27  
Status: implementado — consolidação governada da runtime intelligence mesh

## Objetivo

Executar consolidação governada dos workflows GitHub Actions para:

1. mapear workflows com risco de `No jobs were run`;
2. classificar: órfão, redundante, trigger inválido, experimental, skip governado, regressão real;
3. reduzir duplicidade de pipelines especializados;
4. revisar `on:`, `if:`, `paths:`, `needs:`;
5. separar erro real, skip esperado e workflow informativo;
6. consolidar runtime intelligence mesh em hub central;
7. impedir geração massiva de notificações falsas.

## Componentes

| Componente | Caminho | Função |
|---|---|---|
| Registry | `config/workflow-governance-registry.json` | Classificação canônica e listas de supressão |
| Analisador | `scripts/workflow_governance_consolidator.py` | Mapeamento estático local de workflows |
| Hub mesh | `.github/workflows/operational-runtime-mesh-hub.yml` | Entrada central da runtime intelligence mesh |
| Gerador hub | `scripts/operational_runtime_mesh_hub.py` | Artifact JSON/MD/HTML consolidado |
| Workflow | `.github/workflows/workflow-governance-consolidator.yml` | Publica relatório `workflow-governance-consolidation` |

## Classificações

| Classe | Significado | Ação |
|---|---|---|
| `critical` | Regressão real; bloqueia merge | Alertar |
| `informative` | Evidência/relatório | Suprimir alertas em sucesso |
| `mesh_central` | Hub consolidado | Entrada única da mesh |
| `mesh_redundant` | Cascata mesh legada | Remover `workflow_run` |
| `mesh_legacy_dispatch` | Auditoria manual | Manter só `workflow_dispatch` |
| `governed_skip` | Skip por paths/if esperado | Não alertar |
| `experimental` | Fora do menu diário | Observar |
| `orphan` | Sem trigger efetivo | Revisar ou arquivar |

## Consolidação da mesh

### Antes (cascata)

```text
Post Merge / Monitorador
  → CI Incident Intelligence
    → Operational Stability Score
      → Workflow Reliability Analytics
        → Operational Data Lake
          → Executive Dashboard Generator
            → Live Control Center
              → Realtime Event Mesh / Realtime Mesh / Streaming Layer
                → Alert Intelligence
                  → Unified Event Bus
```

### Depois (hub central)

```text
Fontes primárias (Post Merge, Monitorador, CI Incident, etc.)
  → Operational Runtime Mesh Hub (consolidado)
    → Operational Alert Intelligence (com supressão)
      → Unified Operational Event Bus (com supressão)
```

### Workflows descontinuados para `workflow_run`

- `operational-realtime-event-mesh.yml`
- `realtime-operational-mesh.yml`
- `realtime-operational-streaming-layer.yml`
- `live-operational-control-center.yml`

## Separação erro real vs skip vs informativo

| Tipo | Exemplo | Tratamento |
|---|---|---|
| Regressão real | `CI — ReqSys v2 Enterprise` failure | `OPS-GAP-*`, bloquear merge |
| Skip governado | PR fora de `paths:` | Documentar; não alertar |
| Informativo | Mesh hub success | `governed_skip`; suprimir event bus |

## Comandos locais

```bash
python scripts/workflow_governance_consolidator.py
python scripts/operational_runtime_mesh_hub.py \
  --source-workflow "Post Merge Operational Summary" \
  --source-conclusion success \
  --out-dir artifacts/operational-runtime-mesh-hub
python -m pytest tests/test_workflow_governance_consolidator.py -v
```

## Leitura operacional preferencial

Continua sendo `coordenador-status-evidence`. O relatório de consolidação complementa investigações de pipeline e deve ser lido quando houver suspeita de cascata ou `No jobs were run`.

## Critérios de aceite

- [x] Registry governado versionado
- [x] Analisador local executável
- [x] Hub mesh central com gate anti-cascata
- [x] Workflows mesh redundantes sem `workflow_run`
- [x] Event bus e alert intelligence com supressão de ruído
- [x] Testes unitários focados
- [x] Documentação operacional
- [x] Disparo pós-merge em `main` via `push` (gera artifact `workflow-governance-consolidation`)

## Referências

- [coordenador-principal-menu-operacional.md](../runbooks/coordenador-principal-menu-operacional.md)
- [ADR-034](../adr/ADR-034-autonomous-operational-runtime-consolidation.md)
- [OPERATIONAL_INTELLIGENCE_HUB_P0.md](../OPERATIONAL_INTELLIGENCE_HUB_P0.md)
