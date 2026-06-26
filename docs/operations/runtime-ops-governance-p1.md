# Runtime Ops Governance P1

## Objetivo

Consolidar o primeiro incremento governado de operação autônoma do ReqSys, reduzindo reruns manuais, drift entre ambientes e retrabalho operacional.

## Entregas

1. **Runtime Health Center**: agrega evidências locais de CI, workflows, PRs, Fly.io, ambientes, cobertura, drift e analytics.
2. **CI Auto Remediation**: define taxonomia de falhas, política de rerun seguro e escopo permitido para autocorreções leves.
3. **Environment Drift Detector**: padroniza comparação dev/hml/prod/Fly.io sem persistir valores de segredos.
4. **Runtime Evidence Consolidator**: gera snapshots JSON, Markdown e HTML para auditoria e relato executivo.
5. **Runtime Governance Engine**: calcula health score, confidence de deploy, política de rollback e limites operacionais.

## Estado atual do P1

| Campo | Valor |
|---|---|
| Modo | `review_only` |
| Estado calculado | `NOT_READY` |
| Health score inicial | 46 |
| Deployment confidence | `low` |
| Próximo incremento | `runtime-ops-governance-p2-live-connectors` |

## Comando operacional

```bash
python tools/product_intelligence/generate_runtime_ops_governance_p1.py
```

## Guardrails

- Não executa deploy.
- Não escreve em sistemas externos.
- Não captura valores de segredos.
- Não faz merge automático.
- Exige revisão humana antes de promoção de ambiente.
