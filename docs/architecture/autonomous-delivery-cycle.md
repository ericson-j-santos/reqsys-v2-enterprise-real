# ADR — Autonomous Delivery Cycle

## Status

Proposto para validação incremental.

## Contexto

O repositório já possui validações de PR, fila governada de merge e automação manual de merge governado. A lacuna é fechar o ciclo quando o PR estiver verde: mergear com segurança, observar o CI pós-merge e capturar o próximo incremento natural.

## Decisão

Adicionar o workflow `.github/workflows/autonomous-delivery-cycle.yml`.

A automação deve:

- processar no máximo 1 PR por ciclo por padrão;
- exigir label explícita `cycle:auto-merge-approved`;
- exigir label `merge-queue:eligible`;
- exigir todos os workflows obrigatórios verdes;
- executar squash merge com SHA esperado;
- observar workflows de `push` no merge commit;
- capturar próximos incrementos como report-only.

## Guardrails

- Merge somente com label explícita.
- Merge somente com `merge-queue:eligible`.
- Merge somente com workflow obrigatório concluído com sucesso.
- Próximo incremento apenas em fila report-only.

## Próximo incremento natural

Consumir o resultado do ciclo no dashboard operacional com cards de ciclo, PR candidato, bloqueios, pós-merge e fila de incrementos.
