# Autonomous Delivery Cycle — contratos de dados

## `autonomous-delivery-cycle-latest.json`

Estado mais recente do ciclo governado.

Campos principais:

- `mode`: `dry_run`, `merge_enabled` ou `seed`.
- `candidate_count`: PRs encontrados com label de ciclo.
- `eligible_count`: PRs elegíveis após validação.
- `merged_count`: PRs efetivamente mergeados.
- `decisions`: decisão detalhada por PR.
- `next_increments`: próximos incrementos extraídos do corpo dos PRs processados.
- `guardrails`: regras de segurança aplicadas.

## `autonomous-delivery-cycle-next-increments.json`

Fila report-only para continuidade no chat/agente.

Campos principais:

- `queue`: lista de incrementos capturados.
- `status`: `queued`, `empty` ou `empty_seed`.
- `source`: origem da fila.
- `guardrails`: regras que impedem execução automática cega.

## Interpretação executiva

- `merged_count > 0`: houve entrega consolidada.
- `post_merge.status = post_merge_attention_required`: revisar CI pós-merge antes de novo incremento.
- `queue.length > 0`: existe próximo incremento sugerido, mas ainda exige validação contextual antes de execução.
