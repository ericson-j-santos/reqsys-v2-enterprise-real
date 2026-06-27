# Runbook — Governed PR Automation

## Objetivo

Automatizar a validação de PRs verdes e permitir merge governado sem depender do `allow_auto_merge` nativo do GitHub.

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

## Entradas

| Entrada | Obrigatória | Padrão | Finalidade |
|---|---:|---|---|
| `pr_number` | Sim | — | PR a validar |
| `execute_merge` | Sim | `false` | Executa merge somente quando `true` |
| `merge_mode` | Sim | `governed_squash` | `governed_squash` ou `native_auto_merge` (este último exige `allow_auto_merge=true`) |
| `required_label` | Sim | `governed-merge-approved` | Label obrigatória para autorizar merge |

## Gates obrigatórios

A automação valida os workflows mais recentes do head SHA do PR:

- `CI Enterprise Fast`
- `CI — ReqSys v2 Enterprise`
- `Governance Quality Gates`
- `Governança Padrão Ouro`
- `Branch Protection Audit`
- `PR Conflict Guard`
- `Governed Merge Queue`

Também exige a label `merge-queue:eligible` aplicada pelo workflow **Governed Merge Queue**.

## Regras de bloqueio

O PR será bloqueado se:

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
