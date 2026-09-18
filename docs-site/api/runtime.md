# API Runtime

> **Versão:** `0.3.0`  
> **Escopo:** documentação inicial dos contratos runtime, OpenAPI e endpoints de prática GET/POST.

## Objetivo

Padronizar a documentação dos endpoints usados pelo ReqSys para validação operacional, integração com Power Automate e prática de estrutura de dados.

## Artefato OpenAPI

```text
docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json
```

## Endpoints de referência

| Método | Endpoint | Finalidade | Estado documentado |
|---|---|---|---|
| `GET` | `/health` | Health check básico | OpenAPI v0.3.0 |
| `GET` | `/api/runtime/health` | Verificação operacional runtime | OpenAPI v0.3.0 |
| `GET` | `/api/runtime/dashboard` | Sinais operacionais do dashboard runtime | Referência runtime |
| `GET` | `/api/runtime/analytics` | Evidências e analytics operacionais | Referência runtime |
| `GET` | `/api/requisitos/{id}` | Consulta mockada de requisito | OpenAPI v0.3.0 |
| `POST` | `/api/requisitos` | Recebimento/criação mockada de requisito | OpenAPI v0.3.0 |

## Contrato GET — requisito

Exemplo lógico:

```http
GET /api/requisitos/REQ-001
```

Resposta esperada:

```json
{
  "id": "REQ-001",
  "titulo": "Registrar requisito via fluxo automatizado",
  "tipo": "funcional",
  "status": "rascunho",
  "prioridade": "alta",
  "origem": "power_automate",
  "metadata": {
    "versao_contrato": "0.3.0",
    "correlation_id": "reqsys-demo-0001"
  }
}
```

## Contrato POST — requisito

Exemplo lógico:

```http
POST /api/requisitos
Content-Type: application/json
```

Payload mínimo recomendado:

```json
{
  "titulo": "Registrar requisito via Power Automate",
  "descricao": "Fluxo POST para praticar estrutura de dados.",
  "tipo": "funcional",
  "prioridade": "media",
  "origem": "power_automate",
  "metadata": {
    "versao_contrato": "0.3.0",
    "correlation_id": "power-automate-0001"
  }
}
```

## Regras de governança

- Todo payload deve conter versão de contrato.
- Toda resposta operacional deve conter `correlation_id`.
- Dados sensíveis não devem ser logados em claro.
- Campos obrigatórios devem ser validados antes da persistência.
- Quebras de contrato devem ser registradas em changelog.
- Mudanças de contrato devem atualizar o OpenAPI versionado.
