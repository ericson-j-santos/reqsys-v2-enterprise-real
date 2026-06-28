# Power Automate Flow Provisioning P0

## Decisão técnica

O ReqSys não deve criar flows diretamente pelo runtime usando chamadas avulsas ao Flow Maker API. O P0 adota provisionamento governado via ALM:

```text
ReqSys API → GitHub Actions → reqsys-powerplatform-alm → LowCodeFactory → pac solution import → Power Automate
```

## Reuso validado

Antes deste incremento foi identificado o repositório existente:

- `ericson-j-santos/reqsys-powerplatform-alm`
- ativo principal: `scripts/LowCodeFactory.psm1`
- capacidade existente: criação de flow via `pac solution import`
- documentação existente: `SETUP.md`

## Endpoints ReqSys

### Gerar plano sem executar

```http
POST /v1/hub-lowcode/power-automate/flows/provisioning-plan
```

Payload:

```json
{
  "display_name": "ReqSys - Receber Requisito via HTTP",
  "trigger_type": "HttpRequest",
  "description": "Flow HTTP para receber requisito e chamar API ReqSys.",
  "target_environment": "dev",
  "solution_name": "ReqSysAutomacao",
  "dry_run": true
}
```

### Solicitar provisionamento

```http
POST /v1/hub-lowcode/power-automate/flows/provision
```

Este endpoint gera o manifesto e tenta despachar o workflow GitHub Actions. Se `GITHUB_PAT` não estiver configurado, retorna o plano com status pendente sem quebrar o runtime.

## Workflow GitHub Actions

Arquivo:

```text
.github/workflows/power-automate-flow-provisioning-p0.yml
```

Entradas:

| Input | Descrição |
| --- | --- |
| `display_name` | Nome do flow |
| `trigger_type` | `HttpRequest`, `Recurrence` ou `Manual` |
| `target_environment` | `dev`, `test` ou `prod` |
| `solution_name` | Nome da solution, padrão `ReqSysAutomacao` |
| `correlation_id` | Rastreabilidade ReqSys |
| `dry_run` | `true` para validar sem importar |

## Secrets necessários para execução real

| Secret | Uso |
| --- | --- |
| `GH_ALM_TOKEN` | Checkout do repositório ALM, se privado |
| `POWERPLATFORM_APP_ID` | App registration/SPN |
| `POWERPLATFORM_CLIENT_SECRET` | Secret do SPN |
| `POWERPLATFORM_TENANT_ID` | Tenant Microsoft Entra |
| `DEV_ENVIRONMENT_URL` | Dataverse URL DEV |
| `TEST_ENVIRONMENT_URL` | Dataverse URL TEST |
| `PROD_ENVIRONMENT_URL` | Dataverse URL PROD |

## Governança P0

- Reutiliza solução ALM existente.
- Não grava client secret no ReqSys.
- Não cria conexão de usuário automaticamente.
- Gera manifesto versionado.
- Produz artifact JSON de evidência.
- Mantém fallback seguro quando secrets não existem.

## Limites conhecidos

- Flows com conectores que exigem user connection podem ficar em Draft até conexão ser configurada.
- P0 cobre principalmente flows HTTP/HTTP actions sem dependência de conexão de usuário.
- Produção deve exigir aprovação no GitHub Environment antes de `dry_run=false`.
