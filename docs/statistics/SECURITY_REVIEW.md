# Revisão de Segurança — Aba Estatísticas v1

## Escopo analisado

- Serviço frontend de indicadores.
- Tela Vue de estatísticas.
- Uso de fontes internas e externas.
- Regras de guard rails.

## Controles aplicados

| Controle | Status | Observação |
|---|---|---|
| Separação interno/externo | Aplicado | `fonte.tipo` diferencia origem |
| Fórmula obrigatória | Aplicado | `validarIndicador` bloqueia ausência |
| Fonte obrigatória | Aplicado | `validarIndicador` bloqueia ausência |
| TTL para fonte externa | Aplicado | fonte externa exige `ttlMinutos` |
| Evidência para estado avançado | Aplicado | mínimo de duas evidências |
| Mock externo como real | Parcial | política documentada; gate CI fica para v2 |
| Dados sensíveis | Adequado inicial | não há PII, token ou segredo nos indicadores iniciais |

## Riscos residuais

- A v1 ainda não possui backend real nem policy gate em CI.
- A fonte local inicial deve ser substituída por APIs internas reais.
- Indicadores externos devem ser liberados somente após registry/conector autorizado.

## Recomendação

Manter o PR em draft até CI verde e somente promover a maturidade após build/testes e revisão dos fluxos reais de dados.
