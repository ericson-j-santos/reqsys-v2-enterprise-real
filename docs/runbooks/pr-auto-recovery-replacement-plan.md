# PR Auto Recovery Replacement Plan

## Objetivo

Este incremento adiciona uma camada de planejamento para recuperação governada de PRs problemáticos detectados pelo `PR Auto Recovery Diagnostics`.

## Escopo

- Lê o artifact `pr-auto-recovery.json` produzido pelo diagnóstico.
- Seleciona sinais `P0` como candidatos a plano de recuperação.
- Gera `replacement-plan.json` e `replacement-plan.md`.
- Mantém execução em modo `review-only`.
- Publica artifact para auditoria.

## Fora de escopo

- Não cria branches.
- Não abre pull requests substitutos.
- Não fecha pull requests originais.
- Não executa merge.
- Não altera branch protection.
- Não altera permissões.
- Não executa deploy.

## Saídas

Diretório esperado:

```text
artifacts/pr-auto-recovery/
```

Arquivos esperados:

```text
pr-auto-recovery.json
summary.md
replacement-plan.json
replacement-plan.md
```

## Gates de validação

O workflow valida que:

- `mode == draft-replacement-plan-review-only`;
- `mutating_actions_disabled == true`;
- `requires_human_review == true`;
- candidatos são uma lista válida;
- cada candidato exige revisão humana;
- cada branch proposta segue prefixo `bot/recovery/pr-`.

## Próximo incremento recomendado

Implementar criação real de PR substituto em draft somente após gates adicionais explícitos, com allowlist de repositório, proteção contra duplicidade e execução manual supervisionada.
