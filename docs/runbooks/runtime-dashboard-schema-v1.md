# Runtime Dashboard Schema v1

## Objetivo

Expor um contrato JSON para dashboard operacional vivo, navegavel e compativel com Schema-Driven UI.

## Endpoint

- `/api/runtime/dashboard`

## Conteudo

- layout responsivo;
- cards de status, risco, pendencias e uptime;
- drilldowns para runtime health, metricas e monitoramento operacional;
- secoes de smoke publico e evidencias de governanca;
- guardrails explicitos sem secrets e sem PII.

## Critérios de aceite

- endpoint retorna HTTP 200;
- `correlation_id` e propagado;
- schema versionado;
- cards possuem ids estaveis;
- drilldowns usam rotas publicas ou operacionais existentes;
- contrato permanece read-only.

## Impacto esperado

- aumenta maturidade de UX operacional;
- prepara frontend para renderizacao dinamica;
- reduz acoplamento do painel a campos fixos;
- habilita dashboard navegavel sem alterar deploy ou secrets.
