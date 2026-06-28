# UI copy — Autonomous Delivery Cycle

## Título

Autonomous Delivery Cycle

## Subtítulo

Merge governado somente para PRs verdes e explicitamente autorizados.

## Estados

- `seed`: contrato inicial ainda não executado.
- `dry_run`: simulação sem merge.
- `merge_enabled`: execução com merge permitido.
- `post_merge_attention_required`: falha pós-merge exige correção antes do próximo incremento.

## Mensagem de fila vazia

Nenhum próximo incremento capturado no último ciclo.

## Mensagem de bloqueio

O PR ainda não atende todos os critérios para merge automático governado.
