# Power Automate — prática GET/POST no ReqSys

> **Versão:** `0.3.0`  
> **Escopo:** prática controlada de envio e recebimento de payloads via Power Automate usando contratos HTTP versionados.

## Objetivo

Permitir que analistas e desenvolvedores pratiquem dois fluxos essenciais:

1. **GET** — consultar um requisito no ReqSys.
2. **POST** — enviar um requisito estruturado para o ReqSys.

## Fluxo GET — consultar requisito

### Requisição

```http
GET /api/requisitos/REQ-001
Accept: application/json
x-correlation-id: reqsys-pa-get-0001
```

### Resposta esperada

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
    "correlation_id": "reqsys-pa-get-0001"
  }
}
```

## Fluxo POST — enviar requisito

### Requisição

```http
POST /api/requisitos
Content-Type: application/json
Accept: application/json
x-correlation-id: reqsys-pa-post-0001
```

### Payload recomendado

```json
{
  "titulo": "Registrar requisito via Power Automate",
  "descricao": "Fluxo de recebimento POST para praticar estrutura de dados.",
  "tipo": "funcional",
  "prioridade": "media",
  "origem": "power_automate"
}
```

### Resposta esperada

```json
{
  "id": "REQ-PA-0001",
  "status": "recebido",
  "mensagem": "Requisito recebido para validação mockada.",
  "metadata": {
    "versao_contrato": "0.3.0",
    "correlation_id": "reqsys-pa-post-0001"
  }
}
```

## Mapeamento no Power Automate

| Campo | Origem sugerida | Obrigatório | Observação |
|---|---|---:|---|
| `titulo` | Forms / Teams / variável | Sim | Deve ser claro e testável |
| `descricao` | Forms / Teams | Sim | Deve explicar contexto e objetivo |
| `tipo` | Lista controlada | Sim | `funcional`, `nao_funcional`, `regra_negocio`, `restricao` |
| `prioridade` | Lista controlada | Sim | `baixa`, `media`, `alta`, `critica` |
| `origem` | Constante do fluxo | Sim | Ex.: `power_automate` |
| `x-correlation-id` | expressão/guid | Sim | Rastreabilidade ponta a ponta |

## Boas práticas

- Usar ação HTTP com método explícito.
- Gerar `correlation_id` por execução do fluxo.
- Validar campos obrigatórios antes do POST.
- Registrar resposta HTTP para depuração.
- Não incluir dados sensíveis no corpo de teste.
- Separar ambiente DEV de PROD.

## Critérios de aceite

- GET retorna requisito mockado com `metadata.versao_contrato`.
- POST retorna confirmação com `id`, `status` e `correlation_id`.
- Fluxo falha de forma explícita quando campo obrigatório estiver ausente.
- Logs permitem rastrear cada execução pelo mesmo `correlation_id`.
