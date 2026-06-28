# Workflow names registry — Autonomous Delivery Cycle

O workflow usa os nomes abaixo como gates obrigatórios:

```text
CI Enterprise Fast
CI — ReqSys v2 Enterprise
Governance Quality Gates
Governança Padrão Ouro
Branch Protection Audit
PR Conflict Guard
Governed Merge Queue
```

## Manutenção

Se algum workflow for renomeado, atualizar simultaneamente:

- `.github/workflows/autonomous-delivery-cycle.yml`
- `docs/ops-dashboard/data/autonomous-delivery-cycle-policy.json`
- `docs/ops-dashboard/data/autonomous-delivery-cycle-ci-contract.json`
