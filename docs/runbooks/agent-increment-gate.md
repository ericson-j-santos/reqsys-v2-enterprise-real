# Agent Increment Gate

## Objetivo

Automatizar a politica: **nao abrir frentes novas sem incremento objetivo**.

Ciclo operacional:

```text
triagem -> ajuste minimo -> CI completo -> evidencia -> merge controlado
```

## Quando usar

| Momento | Comando / workflow |
|---|---|
| Cloud Agent antes de criar branch | `python scripts/agent_increment_gate.py --increment-type new_front --intent "..."` |
| Corrigir OPS-GAP | `--increment-type gap_fix --reference OPS-GAP-*` |
| Fechar PR duplicado | `--increment-type close_duplicate --reference <numero>` |
| Hotfix escopo fechado | `--increment-type hotfix --reference OPS-GAP-*` |
| Concluir incremento ativo | `--increment-type consolidate` |
| CI / evidencia auditavel | Workflow **Agent Increment Gate** (`workflow_dispatch`) |
| Abertura de PR (runtime) | Workflow **Governed PR Automation** (`pull_request`) |

## Exit codes

| Code | Significado |
|---|---|
| `0` | Incremento permitido |
| `1` | Bloqueado — seguir `recommended_actions` em `coordenador-status.json` |
| `2` | Erro de uso / entrada invalida |

## Artifact

Nome: `agent-increment-gate-evidence`

| Arquivo | Conteudo |
|---|---|
| `agent-increment-gate.json` | Decisao estruturada (`allowed`, `reason`, `increment_gate`) |
| `decision.json` | Copia da saida JSON no workflow |

## Dependencias

Le `coordenador-status.json` (gerado pelo **Coordenador Status Consolidator**), que inclui:

- `increment_gate.new_front_allowed`
- `increment_gate.blockers` (`state_red`, `critical_gaps`, `duplicate_open_prs`, `open_pr_queue_pressure`, `state_yellow`)
- `increment_gate.allowed_increment_types`

## Links

- Menu operacional: [coordenador-principal-menu-operacional](coordenador-principal-menu-operacional.md)
- Consolidador: [coordenador-status-consolidator](coordenador-status-consolidator.md)
- Schema: [coordenador-status.schema.json](../contracts/coordenador-status.schema.json)
