# Changelog — Executive Readiness Security Summary Source

## Resumo

Conectado o `security-executive-summary.json` ao `Executive Readiness Gate` como fonte canônica do domínio de segurança.

## Objetivo

Eliminar duplicidade de cálculo no domínio `seguranca` e garantir que a decisão executiva de readiness consuma a mesma evidência publicada no Ops Dashboard e no artifact `security-executive-summary`.

## Arquivos alterados

- `scripts/executive_readiness_gate.py`
- `tests/test_executive_readiness_gate.py`
- `.github/workflows/executive-readiness-gate.yml`

## Comportamento novo

Ordem de precedência para o domínio `seguranca`:

1. `security_executive_summary`.
2. `security_baseline`.
3. `executive_brief`.

## Contratos lidos

```text
docs/ops-dashboard/data/security-executive-summary.json
artifacts/security-executive-summary/security-executive-summary.json
audit/security/security-executive-summary.json
```

## Regras executivas

- `production_blocked=true` no resumo de segurança torna o domínio `seguranca` vermelho.
- Achado crítico consolidado torna o domínio `seguranca` vermelho.
- Backlog sem crítico mantém domínio amarelo e não gera blocker `seguranca_red`.
- O score do domínio passa a usar o score consolidado pelo resumo executivo.

## Workflow

O workflow `Executive Readiness Gate` passa a gerar `security-executive-summary` antes do readiness gate e publica o artifact auxiliar `security-executive-summary-for-readiness`.

## Guardrails

- Report-only.
- Sem deploy.
- Sem leitura de secrets.
- Sem chamadas externas no gate.
- Sem alteração funcional no runtime.

## Próximo incremento seguro

Expor `executive-readiness-gate.json` no Runtime Executive Index e no Ops Dashboard como fonte visual dedicada de readiness final.