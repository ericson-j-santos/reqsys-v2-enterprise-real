# Rollout — Autonomous Delivery Cycle

## Fase 1 — Merge do incremento

- Validar PR.
- Aguardar CI verde.
- Mergear via fluxo governado existente.

## Fase 2 — Dry-run

- Executar `Autonomous Delivery Cycle` com `dry_run=true`.
- Confirmar artifact e JSONs.
- Ajustar nomes de workflows se necessário.

## Fase 3 — Ativação controlada

- Aplicar `cycle:auto-merge-approved` em um PR pequeno, verde e com `merge-queue:eligible`.
- Executar `dry_run=false` manual.
- Validar pós-merge.

## Fase 4 — Ciclo agendado

- Manter agendamento a cada 30 minutos.
- Processar no máximo 1 PR por ciclo.
- Aumentar capacidade apenas após histórico verde.
