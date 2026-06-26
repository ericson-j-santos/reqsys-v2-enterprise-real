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

## Incremento: Runtime Health Center + Operational Status Aggregator

O Runtime Health Center adiciona um agregador local e read-only para consolidar sinais operacionais existentes sem acessar rede externa, secrets ou ambientes produtivos.

### Artifact

O comando abaixo gera o relatório versionado `runtime-health-report.json`:

```bash
python scripts/runtime_health_center.py --output artifacts/runtime-health-center/runtime-health-report.json
```

### Domínios consolidados

| Domínio | Objetivo |
|---|---|
| `ci_cd` | Detectar presença de workflows e artifacts locais de CI/health quando disponíveis. |
| `evidence_gate` | Reaproveitar o PR Evidence Gate e evidências operacionais sem duplicar sua lógica. |
| `governance` | Validar presença de regras operacionais, gate de governança e documentação P1. |
| `runtime_risk` | Consolidar sinais locais de scoring de risco e estabilidade runtime. |
| `living_architecture` | Reutilizar documentação viva e artifacts locais de drift sem duplicar o drift check. |
| `environment` | Verificar base declarativa local de ambientes e gates de produção. |
| `remediation` | Verificar base governada para remediação segura e análise de falhas. |

Cada domínio é classificado como `missing`, `partial`, `warning` ou `passed`. O relatório também calcula `maturity_percent`, `operational_risk`, `confidence_level`, `next_required_actions` e `gold_standard_status` para acompanhar Runtime Health Center, Operational Status Aggregator, artifact JSON, score consolidado, Environment Drift Detector e Remediation Executor governado.

### CI dedicado

O workflow `Runtime Health Center` executa o agregador em pull requests e publicação manual, validando o JSON e publicando o artifact `runtime-health-report`.

### Guardrails

- Execução local/CI, sem rede externa.
- Não lê secrets nem arquivos `.env`.
- Não executa deploy, rerun, merge ou remediação automática.
- Não altera runtime produtivo.
- Usa somente presença/status de arquivos e artifacts locais existentes.
