# Integração Workflow Efficiency — Estado Único e Executive Readiness

## Objetivo

Consumir a evidência real de homologação do artifact `ops-dashboard-static` e propagá-la para os contratos executivos do ReqSys sem alterar a decisão de produção.

## Contratos enriquecidos

- `runtime-executive-index.json`
- `executive-brief.json`
- `executive-readiness-gate.json`

## Comportamento

A integração adiciona o domínio `workflow_efficiency_homologation` com:

- estado da homologação;
- decisão recebida;
- `correlation_id`;
- hashes SHA-256 do HTML e do contrato;
- quantidade de erros;
- indicador `report_only=true`;
- indicador `production_blocker=false`.

Falhas de homologação são representadas como estado amarelo e não alteram automaticamente `ready_for_production`, blockers existentes ou o estado global de produção.

## Fluxo

1. `Ops Dashboard` publica `ops-dashboard-static`.
2. `Workflow Efficiency Artifact Homologation` valida o artifact real.
3. `Workflow Efficiency State Readiness Integration` baixa a evidência.
4. O pós-processador enriquece cópias auditáveis dos três contratos executivos.
5. O artifact `workflow-efficiency-state-readiness` é retido por 30 dias.

## Promoção futura

A conversão para gate bloqueante exige histórico suficiente, política versionada, threshold explícito, rollback e PR separado.
