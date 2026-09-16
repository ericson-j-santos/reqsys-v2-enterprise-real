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

## Autenticação

O workflow não depende de PAT persistente nem de secret dedicado para disparar o workflow irmão no mesmo repositório.

Usa o `GITHUB_TOKEN` efêmero do próprio job, com permissões mínimas explícitas:

```yaml
permissions:
  contents: read
  actions: write
```

O token existe somente durante a execução do job. Se estiver ausente ou se `actions: write` não for suficiente para o dispatch, o workflow falha fechado e não tenta substituir a credencial por PAT.

`GH_PAT_ACTIONS` não faz parte deste contrato.

## Comportamento automático

No modo automático, o workflow dispara:

```text
public-runtime-evidence.yml
```

com:

```text
public_url=https://reqsys-api.fly.dev
strict=false
publish_comment=false
ref=main
```

`publish_comment=false` é intencional no modo automático para evitar falha operacional por ausência de issue/PR alvo. O modo automático permanece não bloqueante; a validação estrita pode ser solicitada explicitamente via `workflow_dispatch`.

## Critério de aceite

O aceite operacional final continua exigindo evidência do artifact `public-runtime-evidence` e conclusão `success` do workflow `Public Runtime Evidence Gate` no SHA/ref alvo. A simples conclusão do auto-dispatch não comprova o runtime.
