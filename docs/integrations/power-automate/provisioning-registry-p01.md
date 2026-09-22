# Power Automate Flow Provisioning Registry P0.1

## Objetivo

Adicionar registry runtime persistente para provisionamentos Power Automate iniciados pelo ReqSys.

O P0 criou o caminho governado:

```text
ReqSys → GitHub Actions → reqsys-powerplatform-alm → PAC CLI → Power Automate
```

O P0.1 adiciona rastreabilidade operacional por `correlation_id`.

## Modelo de status

| Status | Uso |
| --- | --- |
| `planned` | Manifesto gerado, ainda sem dispatch |
| `dispatched` | Workflow solicitado |
| `running` | Execução em andamento |
| `succeeded` | Provisionamento concluído |
| `failed` | Falha operacional |
| `rollback_required` | Falha com necessidade de rollback/remediação |
| `pending_configuration` | Falta token/secrets/configuração para dispatch |

## Endpoints

### Listar registry

```http
GET /v1/hub-lowcode/power-automate/flows/provisioning-registry
```

Filtros:

- `ambiente`
- `status`
- `limit`

### Resumo executivo

```http
GET /v1/hub-lowcode/power-automate/flows/provisioning-registry/summary
```

Retorna:

- total de provisionamentos;
- distribuição por status;
- distribuição por ambiente;
- taxa de sucesso;
- risco operacional;
- semáforo por ambiente.

### Atualizar status

```http
PATCH /v1/hub-lowcode/power-automate/flows/provisioning-registry/{correlation_id}/status
```

Payload:

```json
{
  "status": "succeeded",
  "workflow_run_url": "https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions",
  "artifact_url": "artifact://power-automate-flow-provisioning-p0/1"
}
```

## Campos persistidos

| Campo | Finalidade |
| --- | --- |
| `correlation_id` | Rastreabilidade ponta a ponta |
| `ambiente` | dev/test/prod |
| `flow_id` | GUID idempotente do flow |
| `flow_display_name` | Nome operacional |
| `workflow_run_url` | Evidência CI/CD |
| `artifact_url` | Evidência técnica |
| `retry_count` | Base para retry governado |
| `manifesto_json` | Contrato gerado |
| `dispatch_json` | Resultado do dispatch |
| `erro` | Mensagem operacional minimizada |

## Próximo incremento recomendado

P0.2 deve conectar o workflow GitHub Actions ao endpoint de atualização de status para fechamento automático de `running/succeeded/failed` com `artifact_url` real.
