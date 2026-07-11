# Nota Pareto — Path-Based Workflow Router

## Decisão

Aplicar filtros por path primeiro nos workflows de maior ruído analítico, sem alterar o gate obrigatório rápido.

## Motivo

O maior atraso observado vem do excesso de workflows disparados em PRs pequenos. O roteamento por path reduz disparos sem exigir Kubernetes, runners self-hosted ou mudança de branch protection neste ciclo.

## Próximo incremento seguro

Depois deste PR estabilizar verde, medir a redução de workflows por PR e expandir o roteamento para outros workflows report-only com baixo risco.
