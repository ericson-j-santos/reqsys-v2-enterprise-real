# Decision log — Autonomous Delivery Cycle

## Decisão 1

Usar label explícita `cycle:auto-merge-approved`.

Motivo: impedir merge automático sem autorização humana/governada.

## Decisão 2

Exigir `merge-queue:eligible`.

Motivo: reutilizar a fila governada já existente e reduzir duplicidade de lógica.

## Decisão 3

Processar no máximo 1 PR por ciclo inicialmente.

Motivo: reduzir risco de múltiplos merges em sequência antes de histórico real.

## Decisão 4

Capturar próximos incrementos como report-only.

Motivo: manter continuidade sem execução cega de novo escopo.
