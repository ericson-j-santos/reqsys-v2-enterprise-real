# Runbook — Governed PR Automation

## Objetivo

Automatizar a validação de PRs verdes, **bloquear abertura de novas frentes** quando `increment_gate.new_front_allowed=false`, e permitir merge governado sem depender do `allow_auto_merge` nativo do GitHub.

## Princípio operacional

O caminho CI-driven executa merge automaticamente quando a `Governed Merge Queue` e todos os workflows obrigatórios estão verdes no HEAD exato, o PR está aberto, não-draft, mergeável e contém `merge-queue:eligible`.

A autorização operacional permanente do owner está nas regras canônicas do ReqSys; não é necessária solicitação ou label adicional por PR. O `workflow_dispatch` permanece como contingência manual e mantém modo `dry-run`.

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
| `workflow_run` da `Governed Merge Queue` | `auto-merge-after-governed-queue` | Revalidar HEAD/gates e executar merge automático sob autorização operacional permanente |

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
- no caminho CI-driven, não possuir `merge-queue:eligible`;
- o HEAD, mergeabilidade ou elegibilidade mudar antes da mutação;
- algum workflow obrigatório estiver ausente;
- algum workflow obrigatório ainda estiver em execução;
- algum workflow obrigatório não estiver com `success`.

## Uso recomendado

### 1. Fluxo normal

Nenhuma ação humana adicional é necessária após abrir a PR. O fluxo normal é:

```text
PR aberta
→ gates obrigatórios no HEAD atual
→ Governed Merge Queue verde
→ merge-queue:eligible
→ revalidação final
→ squash merge automático com SHA esperado
```

### 2. Contingência manual

O `workflow_dispatch` permanece disponível para diagnóstico/dry-run e operação de contingência:

```text
pr_number=<numero>
execute_merge=false
required_label=governed-merge-approved
```

Esse caminho manual não é pré-requisito do auto-merge CI-driven.

## Segurança

- O caminho CI-driven só executa merge após a `Governed Merge Queue` verde e `merge-queue:eligible`.
- Revalida `merge-queue:eligible`, mergeabilidade e o HEAD imediatamente antes da mutação.
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
