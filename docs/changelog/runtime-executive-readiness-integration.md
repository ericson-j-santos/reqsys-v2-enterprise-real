# Runtime Executive Readiness Integration

## Resumo

Integra o `Executive Readiness Gate` ao `Runtime Executive Index`, ao fluxo do Ops Dashboard e à camada visual pública, tornando a decisão `READY_FOR_PRODUCTION` / `BLOCKED_FOR_PRODUCTION` consumível por dashboards, automações, agentes e operadores.

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
  - Injeta os cards visuais nos painéis públicos.
  - Publica artifact dedicado `executive-readiness-gate`.

- `scripts/inject_runtime_executive_readiness_cards.py`
  - Injeta card visual de Executive Readiness no `docs/ops-dashboard/index.html`.
  - Injeta seção dedicada no `docs/ops-dashboard/runtime-executive.html`.
  - Mantém injeção idempotente e offline.

- `scripts/validate_runtime_executive_readiness_integration.py`
  - Valida presença do card executivo no contrato.
  - Valida consistência entre summary e card.
  - Valida link e guardrail de precedência.

- `scripts/validate_runtime_executive_readiness_visual.py`
  - Valida presença do card visual nos dois HTMLs públicos.
  - Valida IDs usados pela renderização JavaScript.
  - Valida consumo de `cards.executive_readiness`.

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

## Visual adicionado

- Decisão executiva.
- Produção liberada/bloqueada.
- Score de readiness.
- Risco operacional.
- Quantidade de blockers.
- Domínios obrigatórios.
- Links para `runtime-executive-index.json`, `executive-readiness-gate` e Executive Brief.

## Guardrails

- Execução offline.
- Sem chamada GitHub API em runtime público.
- Sem secrets.
- Sem deploy.
- Sem merge automático por este workflow.
- Precedência explícita do Executive Readiness Gate para decisão de produção.
- Interface consome somente `runtime-executive-index.json`.

## Próximo incremento seguro

Após CI verde e merge, consolidar o mesmo sinal como indicador de topo no relatório executivo enxuto e nos gates externos de promoção DEV → STG → PROD.
