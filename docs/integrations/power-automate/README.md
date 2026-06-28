# ReqSys Power Automate Requisitos API

Contrato de prática para fluxos HTTP do Power Automate.

## Endpoints

| Método | Endpoint | Uso |
| --- | --- | --- |
| GET | `/api/requisitos` | Consultar coleção de requisitos |
| GET | `/api/requisitos/{codigo}` | Consultar requisito por código ou id |
| POST | `/api/requisitos` | Receber requisito enviado por Power Automate |

> Compatibilidade preservada: os endpoints existentes em `/v1/requisitos` continuam ativos.

## Headers recomendados

```http
Accept: application/json
Content-Type: application/json
X-Correlation-Id: REQSYS-PA-DEV-0001
```

## POST `/api/requisitos`

```json
{
  "schema_version": "1.0.0",
  "titulo": "Validar campos obrigatórios",
  "descricao": "O sistema deve impedir o envio de requisitos sem título e descrição.",
  "tipo": "funcional",
  "prioridade": "alta",
  "area": "Arquitetura",
  "sistema": "ReqSys",
  "solicitante": "Power Automate",
  "impacto_regulatorio": false
}
```

## GET `/api/requisitos/{codigo}`

```http
GET /api/requisitos/REQ-123456789
```

## Envelope padrão

```json
{
  "success": true,
  "data": {
    "schema_version": "1.0.0",
    "id": 1,
    "codigo": "REQ-123456789",
    "titulo": "Validar campos obrigatórios",
    "descricao": "O sistema deve impedir o envio de requisitos sem título e descrição.",
    "tipo": "funcional",
    "prioridade": "alta",
    "status": "recebido",
    "area": "Arquitetura",
    "sistema": "ReqSys",
    "solicitante": "Power Automate",
    "impacto_regulatorio": false
  },
  "errors": [],
  "meta": {
    "correlation_id": "REQSYS-PA-DEV-0001",
    "contract": "reqsys-power-automate-requisitos"
  }
}
```

## Prática no Power Automate

### Fluxo POST — envio para ReqSys

1. Criar fluxo manual ou agendado.
2. Adicionar ação `HTTP`.
3. Method: `POST`.
4. URI: `https://reqsys-api.fly.dev/api/requisitos`.
5. Enviar o body do exemplo.
6. Validar retorno `201`.

### Fluxo GET — consulta no ReqSys

1. Adicionar ação `HTTP`.
2. Method: `GET`.
3. URI: `https://reqsys-api.fly.dev/api/requisitos/{codigo}`.
4. Adicionar `Parse JSON` usando o envelope padrão.
5. Usar `data.codigo`, `data.titulo`, `data.status` e `meta.correlation_id`.

## Governança

- `schema_version` obrigatório para versionamento do payload.
- `X-Correlation-Id` recomendado para rastreabilidade ponta a ponta.
- Logs estruturados por origem (`power_automate`) e código do requisito.
- Auditoria minimizada, sem persistir payload completo sensível.
