# ReqSys Copilot Studio Multiagent - STG Validation

Data local: 2026-07-14  
Ambiente STG/Test: `ReqSys Test`  
URL: `https://orgf2ca7436.crm2.dynamics.com/`

## Resultado

Status: validado em STG/Test para smoke estrutural, ALM governado e leitura funcional app-only dos flows.

## Pacote promovido

- Origem: DEV/sandbox `tieri (default)` (`https://orga258f260.crm2.dynamics.com/`)
- Solution: `ReqSysLowCodeCopilot`
- Pacote gerenciado: `ReqSysLowCodeCopilot_stg_managed.zip`
- Pacote unmanaged: `ReqSysLowCodeCopilot_stg_unmanaged.zip`
- Checker managed: 0 Critical, 0 High, 0 Medium, 0 Low, 0 Informational
- Import no STG/Test: concluido com sucesso
- Publicacao de customizacoes: concluida com sucesso

## Evidencia STG/Test

### Solution

Comando:

```powershell
pac solution list --environment https://orgf2ca7436.crm2.dynamics.com/
```

Resultado relevante:

| Unique Name | Friendly Name | Version | Managed |
| --- | --- | --- | --- |
| `ReqSysLowCodeCopilot` | `ReqSysLowCodeCopilot` | `1.0` | `True` |

### Copilot Studio

Comando:

```powershell
pac copilot list --environment https://orgf2ca7436.crm2.dynamics.com/
```

Resultado relevante:

| Name | Copilot ID | Component State | Managed | Status Code | State Code |
| --- | --- | --- | --- | --- | --- |
| `ReqSys Copilot Studio Orquestrador` | `5da35c84-3153-4b22-857c-56dc6415365e` | `Published` | `True` | `Active` | `Provisioned` |

### Workflows Power Automate

Consulta usada:

```powershell
pac env fetch --environment https://orgf2ca7436.crm2.dynamics.com/ --xmlFile fetch-stg-workflows.xml
```

Resultado:

| Flow | Workflow ID | Solution | State | Status |
| --- | --- | --- | --- | --- |
| `ReqSys - Aprovacao de requisito` | `780422ae-8c74-57fc-8895-04f7f3513c33` | `ReqSysLowCodeCopilot` | `Ativado` | `Ativado` |
| `ReqSys - Release governance` | `768fde7b-db2e-500f-8be1-7b4cbf1ed31e` | `ReqSysLowCodeCopilot` | `Ativado` | `Ativado` |
| `ReqSys - Intake de demanda` | `ae83d82a-8e04-5eb4-bf4a-dfadd5443a7a` | `ReqSysLowCodeCopilot` | `Ativado` | `Ativado` |
| `ReqSys - Consulta de status` | `69a54f8b-caec-53c4-9f5b-887230cf43d2` | `ReqSysLowCodeCopilot` | `Ativado` | `Ativado` |

## Correcao de identidade STG

O app/service principal usado pelo backend (`AZURE_CLIENT_ID=4061c542-cdc1-4007-ab57-40ab8f9109fc`) foi associado ao ambiente `ReqSys Test` como application user com a role `System Customizer`:

```powershell
pac admin assign-user --environment https://orgf2ca7436.crm2.dynamics.com/ --user 4061c542-cdc1-4007-ab57-40ab8f9109fc --role "System Customizer" --application-user
```

Resultado: a Flow API deixou de retornar `XrmApplyUserFailed / UserNotInActiveDirectory` e passou a responder `200` para os flows gerenciados do STG/Test.

## Smoke funcional

Passou:

- import managed em STG/Test;
- publicacao de customizacoes;
- Copilot presente, managed, published, active e provisioned;
- workflows presentes na solution e ativados;
- Flow API app-only consegue ler os quatro flows finais, todos com:
  - `state = Started`;
  - `componentState = Published`;
  - `isManaged = true`;
  - `triggerSchema` com `correlation_id` obrigatorio.

Nao executado como chamada HTTP de trigger real:

- a API de gerenciamento confirmou definicao e estado dos flows com a identidade app-only;
- o endpoint publico de trigger HTTP nao foi extraido/executado nesta rodada;
- proxima correcao antes de PROD: executar chamada real de trigger por URL callback ou via acao Copilot Studio, preservando `correlation_id`.

## Decisao

Pode continuar para correcoes em STG/Test, especialmente:

- estender o custom connector com as operacoes finais;
- validar RBAC real do Copilot Studio com grupo/usuario autorizado.

Nao promover para PROD ainda sem smoke HTTP real por trigger/action e validacao de RBAC no STG/Test.
