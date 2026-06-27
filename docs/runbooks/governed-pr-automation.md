# Runbook — Governed PR Automation

## Objetivo

Automatizar a validação de PRs verdes, **bloquear abertura de novas frentes** quando `increment_gate.new_front_allowed=false`, e permitir merge governado sem depender do `allow_auto_merge` nativo do GitHub.

## Princípio operacional

A automação não faz merge por padrão.

O modo padrão é `dry-run`, usado para validar se o PR está elegível.

## Workflow

Arquivo:

```text
.github/workflows/governed-pr-automation.yml
```

Nome:

```text
Governed PR Automation
```

## Gatilhos

| Evento | Job | Finalidade |
|---|---|---|
| `pull_request` (`opened`, `reopened`, `ready_for_review`, `labeled`) | `increment-gate-on-open` | Bloquear abertura quando `new_front_allowed=false` |
| `workflow_dispatch` | `governed-pr-check` | Validar merge + executar squash merge opcional |

## Entradas (`workflow_dispatch`)

| Entrada | Obrigatória | Padrão | Finalidade |
|---|---:|---|---|
| `pr_number` | Sim | — | PR a validar |
| `execute_merge` | Sim | `false` | Executa merge somente quando `true` |
| `required_label` | Sim | `governed-merge-approved` | Label obrigatória para autorizar merge |

## Gates obrigatórios

A automação valida os workflows mais recentes do head SHA do PR:

- `CI Enterprise Fast`
- `CI — ReqSys v2 Enterprise`
- `Governance Quality Gates`
- `Governança Padrão Ouro`
- `Branch Protection Audit`
- `PR Conflict Guard`

## Increment gate (abertura de PR)

Na abertura do PR, o workflow consolida `coordenador-status.json` e executa `scripts/governed_pr_increment_gate.py`:

- Infere `increment_type` (default: `new_front`) a partir de labels, corpo, título e branch.
- Bloqueia quando `new_front_allowed=false` e o PR é classificado como nova frente.
- Permite PRs de `gap_fix`, `hotfix`, `consolidate` ou `close_duplicate` conforme `increment_gate.allowed_increment_types`.

### Declarar tipo de incremento no PR

| Mecanismo | Exemplo |
|---|---|
| Label | `increment:gap_fix`, `increment:hotfix`, `increment:consolidate`, `increment:close_duplicate` |
| Corpo do PR | `increment-type: gap_fix` + referência `OPS-GAP-*` quando aplicável |

Artifact: `governed-pr-increment-gate-evidence` (`governed-pr-increment-gate.json`).

Runbook relacionado: [agent-increment-gate](agent-increment-gate.md).

## Regras de bloqueio (merge)

O PR será bloqueado no merge se:

- o increment gate reprovar o tipo inferido do PR;
- estiver fechado;
- estiver em draft;
- não estiver mergeable;
- não possuir a label obrigatória;
- algum workflow obrigatório estiver ausente;
- algum workflow obrigatório ainda estiver em execução;
- algum workflow obrigatório não estiver com `success`.

## Uso recomendado

### 1. Validação sem merge

Executar manualmente com:

```text
pr_number=<numero>
execute_merge=false
required_label=governed-merge-approved
```

### 2. Aprovação explícita

Adicionar a label:

```text
governed-merge-approved
```

### 3. Merge governado

Executar novamente com:

```text
pr_number=<numero>
execute_merge=true
required_label=governed-merge-approved
```

## Segurança

- Não executa merge sem label obrigatória.
- Não executa merge em PR draft.
- Não executa merge com CI pendente.
- Não executa merge com CI vermelho.
- Usa squash merge.
- Usa head SHA esperado para evitar race condition.

## Limitações

- Não substitui revisão humana em mudanças sensíveis.
- Não habilita auto-merge nativo do repositório.
- Não deve ser usado para PRs com alteração de produção sem revisão explícita.

## Evolução recomendada

- Criar label separada para `governed-dry-run-ok`.
- Registrar relatório em artifact JSON.
- Integrar com Operational Actions Center.
- Adicionar allowlist de paths para merge automático de docs/CI.
- Bloquear automaticamente se houver alteração em auth, CORS, JWT, secrets ou produção.
