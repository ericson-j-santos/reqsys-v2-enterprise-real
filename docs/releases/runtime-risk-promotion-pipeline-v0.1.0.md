# Release Note — Runtime Risk Scoring + Governed Promotion Pipeline v0.1.0

## Resumo

Adiciona classificação automática de risco por PR e pipeline governado de promoção entre ambientes.

## Entregas

- `.github/workflows/runtime-risk-scoring.yml`
- `.github/workflows/governed-promotion-pipeline.yml`
- `docs/ci/RUNTIME_RISK_AND_PROMOTION_PIPELINE.md`
- `docs/adr/ADR-031-runtime-risk-and-promotion-pipeline.md`

## Segurança operacional

- Produção permanece bloqueada para promoção real.
- Produção exige `change_ticket` e confirmação textual `APROVO-PROD` para simulação.
- Homologação pode receber PR draft de promoção quando a política aprovar.
- Artifacts de evidência são publicados nos workflows.

## Artifacts

- `runtime-risk-scoring-evidence`
- `governed-promotion-evidence`

## Próximo incremento recomendado

Integrar o `risk-score.json` ao Actions Center / Runtime Intelligence para visualização operacional no ReqSys.
