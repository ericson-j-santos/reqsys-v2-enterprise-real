# Importação governada — ReqSys Copilot HITL em DEV

## Objetivo

Importar a Solution unmanaged `ReqSysCopilotHITL` exclusivamente no ambiente DEV, com confirmação manual, credenciais protegidas por GitHub Environment, deployment settings fora do código e smoke test pós-importação.

## Workflow

Arquivo:

```text
.github/workflows/copilot-hitl-dev-import.yml
```

Execução permitida somente por `workflow_dispatch` e confirmação literal:

```text
IMPORT_DEV
```

O job usa o GitHub Environment:

```text
reqsys-power-platform-dev
```

Configure proteção por revisores obrigatórios antes de liberar os secrets.

## Secrets obrigatórios

| Secret | Finalidade |
| --- | --- |
| `POWER_PLATFORM_ENVIRONMENT_URL` | URL HTTPS do ambiente DEV |
| `POWER_PLATFORM_TENANT_ID` | Tenant Microsoft Entra ID |
| `POWER_PLATFORM_CLIENT_ID` | Application ID do service principal |
| `POWER_PLATFORM_CLIENT_SECRET` | Segredo do service principal |
| `POWER_PLATFORM_DEPLOYMENT_SETTINGS_JSON` | Connection references e environment variables preenchidas para DEV |

O service principal deve possuir apenas os privilégios necessários para importar e publicar a Solution no ambiente DEV.

## Guardrails

- Bloqueia URLs que indiquem STG, homologação ou PROD.
- Exige URL HTTPS válida.
- Exige pacote ZIP não vazio.
- Exige todas as connection references preenchidas.
- Exige todas as environment variables preenchidas.
- Não registra IDs de conexão, segredos ou valores de ambiente no repositório.
- Não possui gatilho automático por push, PR ou merge.
- Não importa em STG ou PROD.
- Usa concorrência serial para impedir duas importações DEV simultâneas.

## Fluxo operacional

1. Executar testes do validador e do materializador.
2. Materializar `ReqSysCopilotHITL_unmanaged.zip`.
3. Criar o deployment settings em runtime a partir do secret protegido.
4. Validar destino, pacote e configurações.
5. Publicar bundle intermediário de curta retenção.
6. Validar autenticação do service principal.
7. Importar a Solution no DEV.
8. Consultar as Solutions instaladas com PAC CLI.
9. Exigir presença de `ReqSysCopilotHITL`.
10. Publicar evidência por 30 dias.

## Configuração mínima do deployment settings

O JSON deve seguir o contrato do Power Platform CLI e conter valores reais do ambiente DEV:

```json
{
  "ConnectionReferences": [
    {
      "LogicalName": "reqsys_sharedcommondataserviceforapps",
      "ConnectionId": "<connection-id-do-dev>",
      "ConnectorId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps"
    }
  ],
  "EnvironmentVariables": [
    {
      "SchemaName": "reqsys_ApprovalSlaHours",
      "Value": "24"
    }
  ]
}
```

Não grave esse arquivo preenchido no Git.

## Validação local

```bash
python -m pytest \
  backend/tests/test_validate_copilot_hitl_dev_import.py \
  backend/tests/test_materialize_copilot_hitl_solution.py -q
```

Validação manual dos artefatos:

```bash
python scripts/validate_copilot_hitl_dev_import.py \
  --package artifacts/lowcode-solution-factory/copilot-hitl-agent-network/generated/ReqSysCopilotHITL_unmanaged.zip \
  --settings /caminho/seguro/deployment-settings.dev.json \
  --environment-url https://seu-ambiente-dev.crm.dynamics.com
```

## Critério para próximo incremento

Somente após uma execução DEV verde e evidência do smoke test:

- validar tabelas Dataverse;
- validar connection references ativas;
- validar flows presentes e desabilitados quando aplicável;
- validar agentes/tópicos materializados no Copilot Studio;
- executar cenário ponta a ponta sem escrita externa;
- manter STG e PROD bloqueados.
