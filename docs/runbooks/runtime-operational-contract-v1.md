# Runtime Operational Contract v1

## Objetivo

Padronizar os indicadores operacionais utilizados entre:

- runtime health;
- dashboards executivos;
- CI/CD;
- evidence gate;
- documentação viva;
- scorecards operacionais.

## Campos canônicos

| Campo | Objetivo |
| --- | --- |
| `runtime_score` | Saúde operacional consolidada |
| `maturity_percent` | Maturidade real consolidada |
| `operational_risk` | Risco operacional executivo |
| `readiness_status` | Prontidão operacional incremental |

## Semáforo executivo

| Estado | Interpretação |
| --- | --- |
| green | estável, governado e validado |
| yellow | funcional com gaps controlados |
| red | bloqueio, regressão ou ausência de evidência |

## Regras principais

### runtime_score

- 85-100 → green
- 60-84 → yellow
- 0-59 → red

### maturity_percent

Representa:

- implementação;
- validação;
- evidência;
- governança;
- documentação.

### operational_risk

| Valor | Semáforo |
| --- | --- |
| low | green |
| medium | yellow |
| high | red |
| critical | red |

### readiness_status

| Valor | Semáforo |
| --- | --- |
| ready | green |
| partial | yellow |
| blocked | red |

## Guardrails

- readiness_status nunca deve ser `ready` com CI vermelho.
- operational_risk `critical` bloqueia promoção executiva.
- dashboards e runtime devem usar o mesmo cálculo.
- artifacts devem permanecer machine-readable.

## Próximo incremento recomendado

Adicionar:

- validador automático do contrato;
- integração do contrato ao Runtime Health Center;
- propagação para dashboards executivos;
- evidence graph consolidado.
