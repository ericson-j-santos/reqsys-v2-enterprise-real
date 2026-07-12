# Changelog — Ops Dashboard Security Executive Summary

## Resumo

Exposto o contrato `security-executive-summary.json` como card executivo no Ops Dashboard.

## Objetivo

Permitir que a camada executiva visualize, em painel estático, o estado consolidado dos scanners especializados de segurança, sem depender da leitura individual de artifacts técnicos.

## Arquivos adicionados

- `scripts/inject_ops_dashboard_security_executive_summary_card.py`
- `scripts/validate_ops_dashboard_security_executive_summary_card.py`
- `docs/changelog/ops-dashboard-security-executive-summary.md`

## Arquivo atualizado

- `.github/workflows/ops-dashboard.yml`

## Dados publicados

```text
docs/ops-dashboard/data/security-executive-summary.json
artifacts/security-executive-summary/security-executive-summary.json
artifacts/security-executive-summary/security-executive-summary.md
```

## Card publicado

O card `Segurança — resumo executivo dos scanners` exibe:

- Estado executivo.
- Score de segurança.
- Risco percentual.
- Produção bloqueada.
- Contagem por severidade.
- Scanners disponíveis e achados.
- Scanners sem evidência.
- Correlation ID.
- Drill-down bruto.

## Guardrails

- Dashboard estático.
- Sem GitHub API em runtime público.
- Sem leitura de secrets.
- Sem deploy.
- Sem alteração funcional no runtime.
- Fallback seguro quando o artifact ainda não existe.

## Próximo incremento seguro

Conectar `security-executive-summary.json` ao Executive Readiness Gate como fonte canônica do domínio de segurança.