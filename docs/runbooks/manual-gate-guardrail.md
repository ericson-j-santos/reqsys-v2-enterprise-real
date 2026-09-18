# Manual Gate Guardrail — ReqSys

## Objetivo

Reduzir pendências manuais recorrentes no GitHub sem remover a responsabilidade humana por decisões que exigem aceite explícito.

Este runbook padroniza a validação de gates manuais antes de decisões como:

- retirar PR de draft;
- aprovar merge/squash;
- aceitar mudança de política de CI/review;
- validar promoção controlada de ambiente;
- registrar decisão arquitetural explícita;
- confirmar que uma falha não é apenas erro técnico corrigível por código.

## Workflow

Arquivo:

```text
.github/workflows/manual-gate-guardrail.yml
```

Execução:

```text
Actions → Manual Gate Guardrail → Run workflow
```

Entradas:

| Campo | Uso |
|---|---|
| `pr_number` | Número do PR a validar. |
| `decision` | `validate`, `request-deep-review` ou `record-human-approval`. |
| `approval_note` | Obrigatório quando `decision=record-human-approval`. |

## Guard rails

O workflow bloqueia a decisão quando encontrar:

- PR em draft;
- PR não mergeable;
- check latest pendente, falho, cancelado, expirado ou com ação requerida;
- status commit falho, erro ou pendente;
- workflow latest pendente, falho, expirado ou com ação requerida;
- label `deep-review` sem `Deep Governance Review` verde;
- tentativa de registrar aprovação humana sem justificativa auditável.

## Importante sobre runs cancelados

Runs históricos cancelados podem existir por concorrência. O workflow avalia o estado **latest por nome de check/workflow** para reduzir falso bloqueio operacional, mantendo evidência completa no artifact.

## Artifacts

Cada execução publica:

```text
manual-gate-guardrail-<pr_number>
```

Conteúdo:

| Arquivo | Conteúdo |
|---|---|
| `evidence.json` | Evidência técnica estruturada. |
| `summary.md` | Resumo operacional do gate. |

## Aplicação nos casos atuais

### PR #82 — Cofre / segurança

Usar:

```text
pr_number=82
decision=validate
```

Somente após o gate limpo e revisão humana explícita considerar `ready for review` ou merge.

### PR #101 / Issue #95 — Ollama Local Gateway

O workflow pode validar PRs relacionados, mas não cria repositórios GitHub externos. A criação de `ericson-j-santos/reqsys-ollama-local-gateway` continua dependendo de permissão/ferramenta humana ou outro workflow com escopo administrativo adequado.

### PR #128 — Política CI/review

Usar:

```text
pr_number=128
decision=validate
```

Para registrar aceite humano após validação limpa:

```text
pr_number=128
decision=record-human-approval
approval_note=Aceito a alteração de política de CI/review conforme artifacts e checks do head atual.
```

## Decisão canônica

O workflow não faz merge automático. Ele transforma uma decisão manual subjetiva em uma decisão rastreável baseada em evidência.

Merge, promoção produtiva, aceite de risco e criação de recursos externos continuam exigindo autorização humana explícita.
