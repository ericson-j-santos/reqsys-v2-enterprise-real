# Segurança de merge — Autonomous Delivery Cycle

## Proteção contra corrida

O merge usa o SHA atual do PR:

```text
sha: pr.head.sha
```

Se o PR receber novo commit entre a validação e o merge, a operação falha.

## Proteção contra escopo indevido

O ciclo exige labels explícitas e fila governada.

## Proteção contra CI pendente

Qualquer workflow obrigatório pendente bloqueia o merge.

## Proteção contra CI ausente

Workflow obrigatório ausente também bloqueia o merge.
