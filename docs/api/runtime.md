# API Runtime

> **Versão:** `0.1.0`  
> **Escopo:** documentação inicial dos contratos runtime e endpoints de prática GET/POST.

## Objetivo

Padronizar a documentação dos endpoints usados pelo ReqSys para validação operacional, integração com Power Automate e prática de estrutura de dados.

## Endpoints de referência

| Método | Endpoint | Finalidade | Estado documentado |
|---|---|---|---|
| `GET` | `/api/runtime/health` | Verificação operacional da API | Referência runtime |
| `GET` | `/api/runtime/dashboard` | Sinais operacionais do dashboard runtime | Referência runtime |
| `GET` | `/api/runtime/analytics` | Evidências e analytics operacionais | Referência runtime |
| `GET` | `/api/requisitos/{id}` | Consulta mockada de requisito | Incremento alvo |
| `POST` | `/api/requisitos` | Recebimento/criação mockada de requisito | Incremento alvo |

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
  "criterios_aceite": [
    "Dado um payload válido, quando o fluxo for executado, então o requisito deve ser registrado com correlation_id."
  ],
  "metadata": {
    "versao_contrato": "0.1.0",
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
  "descricao": "Fluxo de recebimento POST para praticar estrutura de dados.",
  "tipo": "funcional",
  "prioridade": "media",
  "origem": "power_automate",
  "solicitante": {
    "nome": "Usuário de negócio",
    "area": "Operação"
  }
}
```

Resposta esperada:

```json
{
  "id": "REQ-MOCK-001",
  "status": "recebido",
  "mensagem": "Requisito recebido com sucesso.",
  "metadata": {
    "versao_contrato": "0.1.0",
    "correlation_id": "reqsys-demo-0002"
  }
}
```

## Regras de governança

- Todo payload deve conter versão de contrato.
- Toda resposta operacional deve conter `correlation_id`.
- Dados sensíveis não devem ser logados em claro.
- Campos obrigatórios devem ser validados antes da persistência.
- Quebras de contrato devem ser registradas em changelog.

## Próximo incremento técnico

Implementar API mockada com:

1. DTO validado.
2. Swagger/OpenAPI.
3. Endpoint `GET /api/requisitos/{id}`.
4. Endpoint `POST /api/requisitos`.
5. Coleção Postman.
6. Exemplos para Power Automate.
