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
## Runtime Health Center P2 — Environment Drift + Evidence Ingestion

O Runtime Health Center passa a emitir contrato `schema_version=1.1.0` com ingestão local e read-only de artifacts operacionais já produzidos por workflows. A coleta não acessa rede externa, não lê arquivos `.env`, não materializa valores sensíveis e não executa deploy.

Novos blocos do `runtime-health-report.json`:

- `ingested_artifacts`: inventário dos artifacts conhecidos e disponíveis localmente, incluindo status normalizado e erro de parse quando aplicável.
- `runtime_operational_evidence_graph`: consolidação mínima do grafo de evidências a partir dos artifacts ingeridos.
- `runtime_risk_scoring`: visão consolidada do domínio de risco runtime combinada ao nível de drift.
- `pr_evidence_gate`: referência ao gate existente, com `duplicated=false` para preservar a arquitetura atual.
- `environment_drift`: detector local que compara `docker-compose.dev.yml`, `docker-compose.test.yml` e `docker-compose.prod.yml` por estrutura operacional, sem ler segredos.
- `base_maturity_percent`: maturidade antes da penalidade de drift.
- `maturity_percent`: maturidade final após penalidade de drift (`none`, `low`, `medium`, `high`).

Classificação de drift:

| Nível | Critério operacional |
| --- | --- |
| `none` | Nenhuma divergência relevante detectada. |
| `low` | Divergência esperada e governada, como chaves operacionais extras de produção sem exposição de segredo. |
| `medium` | Divergência que exige revisão, como ausência de healthcheck produtivo ou desalinhamento de serviços base. |
| `high` | Bloqueio de segurança ou produção, como arquivo ausente, porta direta do backend em produção ou gates produtivos ausentes. |

O drift reduz a maturidade final e pode elevar `operational_risk`. Drift `high` força risco `high`; drift `medium` mantém risco alto quando a maturidade final ainda não atinge patamar robusto; drift `low` impede classificação `low` quando todos os demais sinais estiverem verdes.

## Padrão ouro — parada de expansão horizontal e aprofundamento

A ação operacional padrão ouro passa a ser consolidar capacidades existentes em vez de criar novas frentes paralelas. O contrato `runtime-health-report.json` expõe `gold_standard_depth` com seis eixos de aprofundamento:

| Eixo | Objetivo | Sinal canônico |
|---|---|---|
| `runtime` | Estabilizar execução real, risco e maturidade operacional. | Domínio `runtime_risk`. |
| `observability` | Reutilizar artifacts existentes como fonte de diagnóstico. | `ingested_artifacts`. |
| `operational_ux` | Transformar o relatório em fila de decisão para operadores. | `next_required_actions` e `gold_standard_status`. |
| `live_analytics` | Usar analytics vivos derivados de artifacts já publicados. | Disponibilidade de artifacts operacionais. |
| `environments` | Bloquear promoção quando houver drift médio/alto. | `environment_drift`. |
| `autonomous_operation` | Manter automação governada, assistida e com guardrails. | Domínio `remediation` e lista `guardrails`. |

A regra de operação é: quando `gold_standard_depth.overall_status` não estiver `passed`, corrigir primeiro os eixos em `blockers`, seguindo `operational_focus_order`, antes de adicionar novos dashboards, workflows ou serviços.

O dashboard estático também pode consumir `runtime_gold_standard_depth`, gerado por `scripts/generate_ops_dashboard_data.py` quando o artifact do Runtime Health Center estiver disponível. Isso aprofunda a UX operacional sem criar outra superfície horizontal.
