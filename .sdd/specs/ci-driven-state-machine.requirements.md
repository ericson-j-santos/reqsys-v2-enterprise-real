# CI-driven state machine — abertura governada de PR

## Objetivo
Eliminar polling manual entre READY_FOR_PR e abertura do PR sem ampliar a superfície de workflows.

## Requisitos
1. Reutilizar Governed PR Automation.
2. Reagir a Pre-PR Readiness Gate concluído com sucesso.
3. Abrir PR automaticamente somente para branches opt-in `automation/*`.
4. Revalidar que o HEAD da branch continua igual ao SHA aprovado.
5. Recusar branch atrás/divergente de main.
6. Ser idempotente quando o PR já existir.
7. Não executar deploy/promoção.

## Critérios de aceite
- Pre-PR vermelho/cancelado não abre PR.
- Branch fora de `automation/*` não abre PR.
- HEAD alterado após o gate bloqueia.
- PR existente no mesmo SHA é reutilizado.
- PR criada confirma o mesmo HEAD aprovado.
- O GMQ e Governed PR Automation existentes continuam responsáveis pelos gates e merge.
