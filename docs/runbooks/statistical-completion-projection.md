# Statistical Completion Projection - ReqSys

## Objetivo

Manter uma projecao estatistica de conclusao do ReqSys, governada por contrato,
versionada e consumida pelo command center. O artefato e **report-only** e nao
substitui gates obrigatorios de CI.

## Artefatos governados

| Tipo | Caminho |
|---|---|
| Contrato JSON Schema | `docs/contracts/statistical-completion-projection.schema.json` |
| Builder deterministico | `scripts/statistical_completion_projection.py` |
| Workflow CI | `.github/workflows/statistical-completion-projection.yml` |
| Testes unitarios | `tests/test_statistical_completion_projection.py` |
| Artefato JSON publicado | `audit/projection/statistical-completion-projection.json` |
| Artefato Markdown publicado | `audit/projection/statistical-completion-projection.md` |

## Como executar localmente

```bash
REQSYS_PROJECTION_GENERATED_AT=2026-06-27T03:00:00Z \
  python3 scripts/statistical_completion_projection.py --output-dir audit/projection
```

Para validar o artefato gerado contra o contrato:

```bash
python3 - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft202012Validator

schema = json.loads(Path('docs/contracts/statistical-completion-projection.schema.json').read_text(encoding='utf-8'))
payload = json.loads(Path('audit/projection/statistical-completion-projection.json').read_text(encoding='utf-8'))
Draft202012Validator.check_schema(schema)
errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.path))
if errors:
    raise SystemExit(1)
print('contract_ok')
PY
```

Tests unitarios:

```bash
python3 -m pytest tests/test_statistical_completion_projection.py -q
```

## Modelo do contrato

O payload reflete a leitura executiva consolidada do projeto e expoe:

- `current_state`: status percentual por dimensao do produto.
- `velocity`: cadencia observada de PRs, merges verdes, correcoes CI, paralelismo seguro e lead time.
- `completion_percent`: percentual real de conclusao por indicador.
- `remaining_gaps_percent`: gap residual por area.
- `timelines.conservative` / `timelines.accelerated`: marcos com janela de dias.
- `bottlenecks`: ranking ordenado dos limitantes atuais.
- `risks`: indice estatistico de risco por categoria.
- `trends`: direcao e intensidade dos vetores ativos.
- `final_probability_percent`: probabilidades estatisticas finais por resultado.
- `acceleration_levers`: ganhos marginais que mais aceleram agora.
- `executive_summary` / `headline`: leitura executiva para o command center.

## Regras operacionais

- Atualizar o builder em conjunto com o runbook e o release note quando o
  cenario consolidado mudar.
- Manter `mode = report_only`; nao usar este artefato como bloqueio de merge.
- Nao registrar PII, segredos ou logs sensiveis no payload.
- Determinismo: usar `REQSYS_PROJECTION_GENERATED_AT` em testes e CI quando for
  importante reproduzir o `generated_at`.
- Quando o produto mudar de fase, abrir nova versao em `docs/releases/` e
  incrementar `SCHEMA_VERSION` se houver quebra de contrato.

## Consumo no dashboard

O dashboard dinamico (`docs/dashboard/live-operational-dashboard.dynamic.html`)
consome `audit/projection/statistical-completion-projection.json` com fallback
governado quando o artefato ainda nao foi publicado.

## Proxima evolucao

- Cruzar `completion_percent` com `audit/maturity/operational-maturity-score.json`
  para identificar divergencias entre projecao executiva e maturidade medida.
- Cruzar `velocity` com `audit/ci-lead-time-analytics.json` para reduzir
  discrepancias entre cadencia executiva declarada e a observada pelo CI.
