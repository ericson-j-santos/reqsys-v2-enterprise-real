# Rollback — Autonomous Delivery Cycle

## Desativação rápida

Remover a label dos PRs candidatos:

```text
cycle:auto-merge-approved
```

Sem essa label, o workflow não executa merge.

## Desativação estrutural

Editar `.github/workflows/autonomous-delivery-cycle.yml` e remover ou comentar o bloco `schedule`.

## Sinais para rollback

- merge automático indevido;
- falso positivo em workflow obrigatório;
- falha pós-merge recorrente;
- drift nos nomes de workflows;
- fila de próximos incrementos duplicando itens.

## Recuperação

- Remover labels de autorização.
- Corrigir política/workflow.
- Executar dry-run.
- Reativar apenas após evidência verde.
