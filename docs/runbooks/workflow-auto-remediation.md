# Workflow Auto Remediation

## Objetivo

Aplicar auto-remediacao segura para GitHub Actions, limitada a rerun de failed jobs em workflows allowlisted.

## Modelo operacional

Por padrao, o workflow roda em `dry-run`.

A remediacao real so ocorre quando executado manualmente com:

- `execute=true`
- `max_reruns` definido

## Escopo permitido

A auto-remediacao pode chamar `rerun-failed-jobs` somente para workflows allowlisted.

Allowlist inicial:

- Main Smoke CI
- Main Operational Health
- Workflow Command Center
- Fast CI - Operational Guardrails
- PR Conflict Guard
- Branch Protection Audit
- Governance Quality Gates
- CI Enterprise Fast

## Bloqueios permanentes

Nao remediar automaticamente workflows cujo nome contenha:

- Deploy
- Production
- Fly Deploy
- Release

## Fora de escopo

Este workflow nao:

- executa deploy;
- altera producao;
- altera secrets;
- faz merge;
- altera branch protection;
- aprova environment;
- cria release;
- executa comandos arbitrarios.

## Artifact

Artifact esperado:

`workflow-auto-remediation-evidence`

Conteudo:

- `workflow-auto-remediation.json`
- `summary.md`

## Permissoes

- `contents: read`
- `actions: write`

Motivo de `actions: write`: necessario para reexecutar failed jobs via API.

## Decisao operacional

| Situacao | Acao |
|---|---|
| Dry-run com candidatos | Revisar artifact antes de executar |
| Execute com remediacao | Acompanhar novo run |
| Workflow bloqueado | Tratar como acao humana/manual |
| Falha recorrente apos rerun | Abrir PR de correcao de causa raiz |

## Guard rail

Auto-remediacao nao substitui correcao de causa raiz. Ela apenas reduz perda de tempo em falhas transientes de CI.