# Auto Public Runtime Evidence

## Objetivo

Automatizar a execução do `Public Runtime Evidence Gate` após validações/runtime em `main`, reduzindo dependência de acionamento manual por CLI.

## Workflow

```text
.github/workflows/auto-public-runtime-evidence.yml
```

## Quando executa

1. Automaticamente quando o workflow `ReqSys Fly Runtime P0` concluir com sucesso em `main`.
2. Manualmente por `workflow_dispatch`, quando necessário.

## Secret requerido

```text
GH_PAT_ACTIONS
```

O secret deve permitir `Actions: read/write` no repositório.

## Comportamento automático

No modo automático, o workflow dispara:

```text
public-runtime-evidence.yml
```

com:

```text
public_url=https://reqsys-api.fly.dev
strict=true
publish_comment=false
ref=main
```

`publish_comment=false` é intencional no modo automático para evitar falha operacional por ausência de issue/PR alvo.

## Critério de aceite

O aceite operacional final continua exigindo evidência do artifact `public-runtime-evidence` e conclusão `success` do workflow `Public Runtime Evidence Gate`.
