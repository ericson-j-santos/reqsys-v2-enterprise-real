# Checklist — Autonomous Delivery Cycle

## Antes de autorizar um PR

- [ ] PR está aberto.
- [ ] PR não está em draft.
- [ ] PR está mergeável.
- [ ] PR possui label `merge-queue:eligible`.
- [ ] PR possui label `cycle:auto-merge-approved`.
- [ ] Todos os workflows obrigatórios estão verdes.
- [ ] Mudança é pequena, governada e rastreável.
- [ ] Não há incidente crítico em `main`.

## Depois do merge

- [ ] CI pós-merge observado.
- [ ] Falhas pós-merge tratadas antes de novo incremento.
- [ ] Artifact `autonomous-delivery-cycle-report` publicado.
- [ ] `autonomous-delivery-cycle-latest.json` atualizado.
- [ ] `autonomous-delivery-cycle-next-increments.json` avaliado.

## Critério de parada

Parar o ciclo se qualquer item abaixo ocorrer:

- CI obrigatório vermelho.
- Falha pós-merge em `main`.
- PR com conflito.
- PR de alto risco sem revisão humana.
- Próximo incremento duplicado ou sem evidência.
