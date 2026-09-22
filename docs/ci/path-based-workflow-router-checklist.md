# Checklist — Path-Based Workflow Router

## Antes de promover para branch protection

- [ ] `ReqSys Required Fast Gate` verde em PRs pequenos.
- [ ] `Path-Based Workflow Router Validation` verde.
- [ ] Workflows advisory continuam executáveis por `workflow_dispatch`.
- [ ] PRs com backend/frontend/scripts/workflows ainda disparam os gates analíticos necessários.
- [ ] PRs documentais simples deixam de disparar gates analíticos desnecessários.

## Regra operacional

Não transformar workflows report-only em required checks até estabilizarem com baixo ruído por alguns ciclos.
