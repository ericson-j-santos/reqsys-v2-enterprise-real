# Homologação de componentes — ReqSys Copilot HITL em DEV

## Objetivo

Validar o conteúdo efetivamente instalado no tenant DEV após a importação da Solution `ReqSysCopilotHITL`. O smoke anterior confirma apenas a presença da Solution; esta homologação exporta o pacote real do ambiente e verifica os componentes mínimos do blueprint canônico.

## Workflow

```text
.github/workflows/copilot-hitl-dev-component-homologation.yml
```

A execução é exclusivamente manual, usa o GitHub Environment `reqsys-power-platform-dev` e exige confirmação literal:

```text
HOMOLOGATE_DEV
```

## Contrato validado

- Solution `ReqSysCopilotHITL` presente no DEV;
- Supervisor e agentes Requisitos, BDD, QA, Governança e DevOps;
- tabelas de workflow, transições, aprovações, execuções e outbox;
- sete capacidades de workflow: intake, Analista, Product Owner, Gestor, retomada, dispatcher e SLA;
- pacote exportado válido e inspecionável.

## Evidência

O workflow publica por 90 dias:

- `solution-list.txt`;
- `ReqSysCopilotHITL_DEV_export.zip`;
- `component-homologation.json`.

## Decisão de promoção

A homologação não promove STG ou PROD. O campo `stg_prod_promotion_allowed` permanece `false`, mesmo quando o resultado é `HOMOLOGATED`. A promoção exige incremento separado, aprovação humana e deployment settings próprios por ambiente.

## Resultado esperado

- `HOMOLOGATED`: todos os componentes mínimos foram encontrados no export real do DEV;
- `BLOCKED`/`INCOMPLETE`: a Solution existe, mas o conteúdo importado não materializa integralmente o blueprint.

Esse segundo resultado evidencia o gap entre pacote estrutural e solução funcional, impedindo avanço indevido para STG.
