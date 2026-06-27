# Runbook — Observability Correlation Report

## Objetivo

Gerar, em modo **report-only**, uma visão ponta a ponta que correlaciona workflows, artifacts, dashboards e documentos de runtime health, delivery evidence, readiness, completion e burndown.

## Guardrails

- Não altera backend, frontend produtivo, autenticação, deploy Fly.io ou contratos existentes.
- Não adiciona secrets e não acessa rede.
- Não quebra artifacts existentes: campos não encontrados são publicados como `null`.
- O relatório é evidência operacional, não gate bloqueante por padrão.

## Geração local

```bash
python scripts/observability_correlation_report.py
```

Saídas padrão:

- `artifacts/observability-correlation-report/observability-correlation-report.json`
- `artifacts/observability-correlation-report/observability-correlation-report.md`

## Validação do contrato

```bash
python -m jsonschema -i artifacts/observability-correlation-report/observability-correlation-report.json docs/contracts/observability-correlation-report.schema.json
```

## Integração com dashboard operacional

O dashboard estático lê o relatório quando o arquivo JSON é informado ao gerador:

```bash
python scripts/generate_ops_dashboard_data.py \
  --observability-correlation-report artifacts/observability-correlation-report/observability-correlation-report.json
```

A integração adiciona apenas a seção **Observability Correlation — report-only** ao payload e ao HTML, preservando os cards existentes.

## Interpretação

- `correlation_id`, `workflow_run_id`, `commit_sha`, `branch`, `pr` e `artifact_name` são preenchidos somente quando aparecem nos artifacts ou no contexto Git local.
- `maturity_percent`, `operational_risk` e `confidence_level` são consolidados por melhor esforço e devem ser tratados como sinal de observabilidade, não como decisão automática de deploy.
- Ausência de artifact reduz confiança, mas não muda comportamento funcional.
