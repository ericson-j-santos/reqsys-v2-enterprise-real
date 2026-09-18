# Power Platform Runtime Layer — Pareto Runbook

Versão: `0.1.0`  
Modo: `sandbox-first`, `ALM-first`, `sem secrets no Git`

## Objetivo

Criar a camada de integração segura entre ReqSys e Power Platform, priorizando GET/POST mockados, contrato OpenAPI e governança ALM antes de provisionamento real de flows.

## Sequência recomendada

| Ordem | Incremento | Critério de conclusão |
|---:|---|---|
| 1 | API mockada GET/POST | Payloads versionados e validados |
| 2 | OpenAPI connector | Contrato importável e sem secret |
| 3 | Fluxo Power Automate manual | Flow criado em ambiente DEV/sandbox |
| 4 | Export ALM | Solution exportada e versionada |
| 5 | Provisionamento assistido | Execução via pipeline com aprovação |

## Guardrails

- Não versionar tokens, tenant secrets, client secrets ou connection references reais.
- Não provisionar flows em produção sem aprovação humana.
- Não misturar DEV, HML e PROD na mesma connection reference.
- Não usar endpoints produtivos para testes de contrato.
- Não acoplar fluxo Power Automate a DTO não versionado.

## Contrato mínimo GET

```http
GET /api/power-platform/requisitos/{id}
```

Resposta mínima:

```json
{
  "schema_version": "0.1.0",
  "correlation_id": "REQSYS-DEV-000001",
  "id": "REQ-001",
  "status": "validado",
  "titulo": "Exemplo de requisito",
  "prioridade": "alta",
  "updated_at": "2026-06-29T09:00:00-03:00"
}
```

## Contrato mínimo POST

```http
POST /api/power-platform/respostas
```

Payload mínimo:

```json
{
  "schema_version": "0.1.0",
  "correlation_id": "REQSYS-DEV-000001",
  "origem": "power_automate",
  "requisito_id": "REQ-001",
  "resposta": {
    "status": "recebido",
    "observacao": "Fluxo DEV validado"
  }
}
```

## Evidências esperadas

| Evidência | Caminho recomendado |
|---|---|
| OpenAPI | `docs-site/assets/openapi/reqsys-runtime-openapi-v0.4.0.json` |
| Payload GET | `docs/power-platform/samples/get-requisito-response.json` |
| Payload POST | `docs/power-platform/samples/post-resposta-request.json` |
| Runbook | `docs/runbooks/power-platform-runtime-layer-pareto.md` |
| ALM | `reqsys-alm/` ou solution exportada em pacote próprio |

## Próximo passo técnico

Após estabilização deste runbook, criar os payloads mockados e conectar o contrato OpenAPI ao `openapi-governance-index.json`.