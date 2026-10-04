# Postman — coleção ReqSys Runtime v0.3.0

> **Versão:** `0.3.0`  
> **Escopo:** coleção Postman governada para prática GET/POST, validação manual e futura automação Newman.

## Artefato

| Item | Caminho |
|---|---|
| Coleção Postman | `docs-site/assets/postman/reqsys-runtime-postman-v0.3.0.json` |
| Contrato OpenAPI relacionado | `docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json` |

## Objetivo

Disponibilizar uma coleção importável no Postman para exercitar os endpoints documentados no contrato OpenAPI v0.3.0.

## Requisições incluídas

| Requisição | Método | Endpoint |
|---|---|---|
| Runtime Health | `GET` | `/api/runtime/health` |
| Runtime Dashboard | `GET` | `/api/runtime/dashboard` |
| Runtime Analytics | `GET` | `/api/runtime/analytics` |
| Consultar Requisito Mockado | `GET` | `/api/requisitos/REQ-001` |
| Criar Requisito Mockado | `POST` | `/api/requisitos` |

## Variáveis

| Variável | Valor padrão | Finalidade |
|---|---|---|
| `baseUrl` | `https://reqsys-api.fly.dev` | URL base da API |
| `correlationId` | `reqsys-postman-0001` | Rastreabilidade da execução |

## Guardrails

- Não contém secrets.
- Não contém dados sensíveis reais.
- Usa payload mockado.
- Mantém `x-correlation-id` em todas as chamadas.
- Pode ser evoluída para Newman CI sem alterar o contrato OpenAPI.

## Próximo incremento recomendado

Adicionar validador de coleção Postman e execução Newman opcional em CI, mantendo execução HTTP pública como não bloqueante quando o ambiente externo estiver indisponível.
