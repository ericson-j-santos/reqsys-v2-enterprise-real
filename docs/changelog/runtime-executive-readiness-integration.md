# Runtime Executive Readiness Integration

## Resumo

Integra o `Executive Readiness Gate` ao `Runtime Executive Index` e ao fluxo do Ops Dashboard, tornando a decisão `READY_FOR_PRODUCTION` / `BLOCKED_FOR_PRODUCTION` consumível por dashboards, automações e agentes.

## Alterações

- `scripts/build_runtime_executive_index.py`
  - Eleva o contrato para `schema_version=1.2.0`.
  - Adiciona o card `cards.executive_readiness`.
  - Adiciona `summary.production_ready`.
  - Adiciona `summary.executive_readiness_decision`.
  - Adiciona link `links.executive_readiness_gate`.
  - Dá precedência ao readiness gate na decisão executiva de produção.

- `.github/workflows/ops-dashboard.yml`
  - Gera `artifacts/executive-readiness-gate/executive-readiness-gate.json` antes do Runtime Executive Index.
  - Passa `--executive-readiness` para o builder do índice executivo.
  - Valida o contrato integrado.
  - Publica artifact dedicado `executive-readiness-gate`.

- `scripts/validate_runtime_executive_readiness_integration.py`
  - Valida presença do card executivo.
  - Valida consistência entre summary e card.
  - Valida link e guardrail de precedência.

- `tests/test_runtime_executive_readiness_index.py`
  - Cobre cenário pronto para produção.
  - Cobre cenário bloqueado por blocker executivo.

## Contrato adicionado

```json
{
  "summary": {
    "production_ready": true,
    "executive_readiness_decision": "READY_FOR_PRODUCTION"
  },
  "cards": {
    "executive_readiness": {
      "ready_for_production": true,
      "decision": "READY_FOR_PRODUCTION",
      "score": 100,
      "risk_percent": 0,
      "blockers": []
    }
  }
}
```

## Guardrails

- Execução offline.
- Sem chamada GitHub API em runtime público.
- Sem secrets.
- Sem deploy.
- Sem merge automático por este workflow.
- Precedência explícita do Executive Readiness Gate para decisão de produção.

## Próximo incremento seguro

Expor visualmente `cards.executive_readiness` como card dedicado no HTML público do Ops Dashboard e no `runtime-executive.html`, mantendo o mesmo contrato `runtime-executive-index.json`.
