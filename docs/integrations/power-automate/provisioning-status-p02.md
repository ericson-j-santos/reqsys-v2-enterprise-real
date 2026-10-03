# Power Automate Flow Provisioning Status P0.2

## Objetivo

Conectar o workflow GitHub Actions de provisionamento ao registry runtime do ReqSys.

Antes do P0.2, o registry aceitava atualização manual de status por `correlation_id`. Agora o próprio workflow atualiza automaticamente:

- `running` no início da execução;
- `succeeded` ao final com sucesso;
- `failed` quando o workflow falha.

## Workflow alterado

```text
.github/workflows/power-automate-flow-provisioning-p0.yml
```

## Secrets

| Secret | Obrigatório | Uso |
| --- | --- | --- |
| `REQSYS_API_BASE_URL` | Sim, para callback real | Base URL pública da API ReqSys |
| `REQSYS_PROVISIONING_STATUS_TOKEN` | Opcional | Token Bearer futuro para endpoint protegido |

## Endpoint chamado

```http
PATCH /v1/hub-lowcode/power-automate/flows/provisioning-registry/{correlation_id}/status
```

## Campos atualizados

```json
{
  "status": "running|succeeded|failed",
  "workflow_run_url": "https://github.com/.../actions/runs/...",
  "artifact_url": "https://github.com/.../actions/runs/...#artifacts",
  "erro": "mensagem resumida quando houver falha"
}
```

## Regra operacional

Os callbacks usam `continue-on-error: true`. Assim, uma indisponibilidade temporária do ReqSys não bloqueia a criação do flow no Power Automate.

## Limites conhecidos

- Sem `REQSYS_API_BASE_URL`, o workflow executa sem callback.
- Sem `correlation_id`, o workflow executa sem callback.
- O token é opcional porque o endpoint atual ainda não exige autenticação dedicada.

## Próximo incremento recomendado

P0.3: proteger o endpoint de status com `REQSYS_PROVISIONING_STATUS_TOKEN`, validando Bearer token no backend antes de aceitar atualização de status.
