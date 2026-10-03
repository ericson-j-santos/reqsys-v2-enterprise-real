# Pin de Actions — Environment Observability Promotion

## Objetivo

Eliminar referências mutáveis no workflow de promoção da Environment Observability API,
começando por `superfly/flyctl-actions/setup-flyctl@master`, sem alterar a lógica de
build, deploy, promoção ou ambientes.

## Requisitos

1. Fixar `superfly/flyctl-actions/setup-flyctl` no commit exato apontado por `master`
   no momento da mudança: `ed8efb33836e8b2096c7fd3ba1c8afe303ebbff1`.
2. Fixar também todas as demais Actions externas do mesmo workflow por SHA Git completo,
   satisfazendo o ratchet de imutabilidade já vigente.
3. Preservar inputs, permissões, ambientes, comandos de build, deploy, smoke e artifacts.
4. Não executar deploy como parte desta mudança.
5. Não alterar secrets, environments, permissões administrativas ou configuração Fly.
6. O teste de regressão deve falhar se `@master` retornar.
7. O gate de imutabilidade deve produzir zero violações bloqueantes para o workflow alterado.

## Critérios de aceite

- `tests/test_environment_observability_action_pins.py` verde.
- Controle negativo comprova que `setup-flyctl@master` seria rejeitado.
- Pre-PR Readiness verde no HEAD final e `behind_by=0`.
- Checks da PR verdes no mesmo HEAD antes de merge.
- Após merge, leitura independente da `main` confirma os SHAs fixados.
