# ADR — Autonomous Delivery Cycle

## Status

Proposto para validação incremental.

## Contexto

O fluxo atual já possui:

- validações de PR;
- fila governada de merge;
- automação manual de merge governado;
- evidências operacionais em artifacts.

A lacuna é fechar o ciclo de entrega com segurança: quando o PR estiver verde e explicitamente autorizado, executar merge, observar CI pós-merge e capturar o próximo incremento natural para continuidade.

## Decisão

Adicionar o workflow `.github/workflows/autonomous-delivery-cycle.yml`.

A automação deve ser conservadora:

- processar no máximo 1 PR por ciclo por padrão;
- exigir label explícita `cycle:auto-merge-approved`;
- exigir label `merge-queue:eligible`;
- exigir todos os workflows obrigatórios verdes;
- executar squash merge com SHA esperado;
- observar workflows de `push` no merge commit;
- publicar evidência em JSON;
- capturar próximos incrementos em fila report-only.

## Consequências positivas

- Reduz espera manual para merges triviais e verdes.
- Evita merges sem evidência.
- Produz rastro auditável por execução.
- Prepara continuidade operacional via fila de incrementos.
- Mantém governança e autorização explícita.

## Consequências negativas / riscos

- Runs pós-merge podem ainda estar pendentes na primeira observação.
- Dependência dos nomes dos workflows obrigatórios.
- Requer disciplina de labels.
- Não substitui revisão humana em mudanças de alto risco.

## Guardrails

- Sem merge sem label explícita.
- Sem merge se `merge-queue:eligible` não existir.
- Sem merge com workflow obrigatório pendente/vermelho/ausente.
- Sem force merge.
- Sem rebase automático.
- Sem execução automática de próximo incremento.

## Próximo incremento natural

Integrar `docs/ops-dashboard/data/autonomous-delivery-cycle-latest.json` e `docs/ops-dashboard/data/autonomous-delivery-cycle-next-increments.json` ao dashboard operacional com cards de ciclo, PR candidato, bloqueios, pós-merge e fila de incrementos.
