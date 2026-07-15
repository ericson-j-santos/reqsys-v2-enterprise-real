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

## Secrets do environment `reqsys-power-platform-dev`

O job `homologate-dev` exige 4 secrets nesse GitHub Environment:
`POWER_PLATFORM_ENVIRONMENT_URL`, `POWER_PLATFORM_CLIENT_ID`,
`POWER_PLATFORM_CLIENT_SECRET`, `POWER_PLATFORM_TENANT_ID`.

A app "ReqSys Enterprise" (mesma usada para login/Graph) já tem Application
User no Dataverse do ambiente **ReqSys Dev** (`https://orge9b920f1.crm2.dynamics.com`)
com papel *System Customizer* — confirmado via leitura direta na Dataverse
Web API (`systemusers`/`systemuserroles_association`), sem necessidade de um
app novo. Para reaproveitar essas credenciais e propagar via cofre:

```bash
export REQSYS_ADMIN_TOKEN="<jwt admin>"
export COFRE_API_URL="http://localhost:8000"
python scripts/configurar_copilot_hitl_dev_secrets.py capturar --reuse-azure-app

export COFRE_SERVICE_TOKEN="<vault token>"
python scripts/configurar_copilot_hitl_dev_secrets.py sincronizar
```

O script nunca imprime o valor do client secret; `capturar` grava no cofre
ReqSys, `sincronizar` lê de volta e aplica via `gh secret set --env
reqsys-power-platform-dev`.

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
