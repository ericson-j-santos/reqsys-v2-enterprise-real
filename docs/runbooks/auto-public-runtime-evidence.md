# Auto Public Runtime Evidence

## Objetivo

Automatizar a execução do `Public Runtime Evidence Gate` após a validação/promoção governada do runtime em `main`, sem depender de PAT ou acionamento manual por CLI.

## Workflow

```text
.github/workflows/auto-public-runtime-evidence.yml
```

## Quando executa

1. Automaticamente quando `Fly Automatic Environment Promotion` concluir com sucesso em `main`.
2. Manualmente por `workflow_dispatch`, quando necessário.

## Credencial

O fluxo usa somente o `GITHUB_TOKEN` efêmero do próprio job, com permissões mínimas:

```text
actions: write
contents: read
```

Não requer `GH_PAT_ACTIONS`, App ID ou chave privada da GitHub App.

## Roteamento automático DEV

O provider é lido de:

```text
vars.REQSYS_DEV_RUNTIME_PROVIDER
```

Valores aceitos:

- `fly`: usa `https://reqsys-api.fly.dev`;
- `pc24x7`: usa `vars.PC24X7_DEV_BASE_URL`, obrigatoriamente HTTPS.

Provider inválido, URL PC24x7 ausente ou URL sem HTTPS bloqueiam o dispatch.

## Comportamento automático

O workflow dispara `public-runtime-evidence.yml` com:

```text
strict=true
publish_comment=false
ref=main
```

`publish_comment=false` evita dependência de issue/PR para produzir o artifact operacional.

## Critério de aceite

O aceite operacional final exige:

- `Auto Public Runtime Evidence` em `success`;
- `Public Runtime Evidence Gate` disparado no `main`;
- artifact `public-runtime-evidence`;
- endpoints strict em sucesso;
- nenhum segredo de longa duração usado pelo despachante.
