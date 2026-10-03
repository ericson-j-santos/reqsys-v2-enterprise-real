# PR Auto Recovery Assisted v2

## Objetivo

Automatizar preparação de recovery sem executar mutações reais no repositório.

## Modo

`assisted-dry-run`

## Entradas

- PR aberto;
- estado mergeable;
- workflows críticos;
- diff do PR;
- arquivos alterados.

## Saídas

Artifacts:

- `recovery-plan.json`
- `reapplied-files.json`
- `blocked-files.json`
- `risk-analysis.json`

## Regras

### Pode reaplicar

- documentação;
- frontend;
- scripts locais;
- workflows explicitamente permitidos.

### Não pode reaplicar

- deploy produção;
- secrets;
- terraform produção;
- branch protection;
- CODEOWNERS.

## Estratégia

1. Detectar PR bloqueado.
2. Calcular risco.
3. Separar arquivos permitidos e bloqueados.
4. Simular branch limpa.
5. Simular PR substituto.
6. Gerar evidência.

## Próxima evolução

A v3 poderá abrir PR draft automaticamente mediante gates explícitos e revisão humana.
