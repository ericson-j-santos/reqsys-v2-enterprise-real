# Environment Promotion Readiness Gate

## Objetivo

Converter as evidências do Estado Único ReqSys em uma decisão governada para promoção entre DEV, STG e PROD, sem criar um monitor paralelo ou um falso verde quando fontes obrigatórias estiverem ausentes.

## Decisões

- `approved`: evidências completas e limites atendidos;
- `approved_with_warning`: promoção não bloqueante com desvios ou evidência de fluxo ausente;
- `blocked`: limite, CI, runtime ou fluxo crítico impede uma promoção bloqueante;
- `insufficient_evidence`: fontes mínimas ausentes; nunca deve ser tratado como verde.

## Política inicial

| Ambiente | Prontidão mínima | Cobertura mínima | Modo |
|---|---:|---:|---|
| DEV | 70% | 80% | relatório |
| STG | 85% | 90% | aviso durante estabilização |
| PROD | 95% | 100% | bloqueante |

## Evidências consumidas

- artifact `instrumented-executive-readiness/report.json`;
- artifact JSON mais recente do Flow Completion Monitor;
- estabilidade do CI incorporada ao contrato de prontidão executiva;
- presença das fontes de consumer readiness, runtime validation, merge intelligence e CI lead time.

## Guardrails

- PROD falha quando a decisão não é `approved`;
- ausência de fonte obrigatória gera `insufficient_evidence`;
- DEV e STG não bloqueiam enquanto a política está em estabilização;
- todo resultado é publicado como artifact por 90 dias;
- a decisão registra ambiente, thresholds, razões, warnings e correlation ID quando disponível.

## Critérios para tornar STG bloqueante

1. Pelo menos cinco execuções válidas consecutivas;
2. nenhuma ocorrência de falso bloqueio por indisponibilidade transitória de artifact;
3. tempo adicional do gate inferior a 60 segundos no percentil 95;
4. contrato do Flow Completion Monitor estabilizado e versionado;
5. aprovação explícita de governança técnica.
