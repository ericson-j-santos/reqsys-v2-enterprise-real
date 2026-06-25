# Operational Analytics Persistence v1

## Objetivo

Transformar observabilidade runtime em analytics temporal governado.

## Endpoint

- `/api/runtime/analytics`

## Escopo desta fatia

- rolling store em memoria;
- janela limitada de snapshots;
- failure rate;
- availability score;
- media e maximo de risk score;
- tendencia de risco, pendencias e bloqueios;
- placeholders governados para MTTR e lead time.

## Guardrails

- read-only;
- sem secrets;
- sem PII;
- sem migracao de banco;
- sem alteracao de deploy;
- sem acao destrutiva.

## Limitacao conhecida

Esta versao usa persistencia em memoria. Os dados reiniciam com o processo. A proxima fatia deve adicionar storage duravel e eventos de deploy/incidente.

## Proximo incremento

- modelo duravel `runtime_operational_snapshots`;
- persistencia em banco;
- eventos de incidente;
- calculo real de MTTR;
- integracao com deploy events para lead time.
