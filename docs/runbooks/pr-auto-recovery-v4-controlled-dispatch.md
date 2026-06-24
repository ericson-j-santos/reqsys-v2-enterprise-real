# PR Auto Recovery v4 — Controlled workflow_dispatch

## Objetivo

Permitir execução manual controlada de recovery para um único PR alvo.

## Entradas obrigatórias

- `pr_number`
- `execution_mode`
- `operator_confirmation`

## Modos

### dry-run

Somente gera plano operacional.

### controlled-draft-only

Reservado para futura abertura controlada de PR draft substituto.

## Segurança

A v4 continua bloqueando:

- merge automático;
- fechamento automático do PR original;
- deploy;
- alteração de secrets;
- alteração de branch protection.

## Artifact

Artifact esperado:

`pr-auto-recovery-controlled`

Conteúdo:

- `execution-plan.json`

## Fluxo operacional

1. Operador inicia workflow manual.
2. Workflow valida confirmação explícita.
3. Workflow valida gates versionados.
4. Workflow gera plano controlado.
5. Workflow publica artifact.
6. Revisão humana decide próximo passo.
