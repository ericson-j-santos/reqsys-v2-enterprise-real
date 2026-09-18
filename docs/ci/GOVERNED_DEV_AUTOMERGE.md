# Governed Dev Auto Merge

## Decisão

Adotar automação governada apenas para ambiente `dev`, mantendo homologação e produção sob promoção manual/governada.

## Estratégia

```text
feature/*
  ↓ PR para dev
  ↓ CI + policy + aprovação opcional
  ↓ workflow manual Governed Dev Auto Merge
  ↓ merge squash em dev
  ↓ homologação via promotion governada
  ↓ produção com aprovação humana explícita
```

## O que o workflow automatiza

- Validação do PR informado manualmente.
- Leitura dos metadados do PR.
- Coleta dos arquivos alterados.
- Classificação de risco.
- Bloqueio de auto-merge para mudanças sensíveis.
- Publicação de artifact de evidência.
- Merge squash em `dev` somente quando permitido e `dry_run=false`.

## Áreas bloqueadas para auto-merge em dev

O workflow bloqueia auto-merge quando detectar alterações relacionadas a:

- autenticação;
- segurança;
- secrets/cofre/vault;
- JWT;
- CORS;
- deploy;
- Fly.io;
- infra;
- migrações/banco;
- produção;
- homologação;
- release;
- workflows de deploy/release/prod;
- arquivos `.env`;
- indicadores de escopo produtivo.

## Ambientes

| Ambiente | Estratégia |
|---|---|
| `dev` | Auto-merge governado permitido para baixo risco |
| `homolog` | Promotion governada/manual |
| `prod` | Aprovação humana explícita obrigatória |

## Uso operacional

Executar manualmente em GitHub Actions:

```text
Governed Dev Auto Merge
```

Inputs:

| Input | Uso |
|---|---|
| `pr_number` | Número do PR a avaliar |
| `dry_run` | `true` para somente validar; `false` para permitir merge |
| `require_manual_approval` | `true` para exigir review aprovado |

## Regras de segurança

- O workflow não atua em PRs para `main`, `homolog` ou `prod`.
- O workflow exige que a base do PR seja `dev`.
- O workflow publica evidência em artifact.
- O workflow não substitui aprovação de produção.
- O workflow não deve ser usado para mudanças sensíveis.

## Critério para uso real

Antes de usar com `dry_run=false`:

- validar CI do próprio workflow;
- confirmar existência da branch `dev`;
- revisar branch protection aplicável;
- definir se `require_manual_approval=true` será obrigatório;
- validar o artifact `governed-dev-automerge-evidence`.
