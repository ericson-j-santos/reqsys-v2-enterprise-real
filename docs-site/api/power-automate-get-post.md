# Power Automate — GET e POST

> **Versão:** `0.3.0`  
> **Objetivo:** praticar envio e recebimento de dados usando Power Automate com contratos ReqSys.

## Fluxo 1 — GET de requisito

### Finalidade

Consultar um requisito mockado pelo identificador e usar a resposta no fluxo.

### Requisição

```http
GET https://reqsys-api.fly.dev/api/requisitos/REQ-001
Accept: application/json
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
    "correlation_id": "reqsys-demo-0001"
  }
}
```

### Estrutura recomendada no Power Automate

| Etapa | Ação | Observação |
|---|---|---|
| 1 | Manual trigger | Informar `id` do requisito |
| 2 | HTTP GET | Chamar `/api/requisitos/{id}` |
| 3 | Parse JSON | Usar schema derivado da resposta |
| 4 | Compose/Condition | Validar `status`, `tipo` e `prioridade` |
| 5 | Log operacional | Guardar `correlation_id` |

## Fluxo 2 — POST de requisito

### Finalidade

Enviar um requisito para o endpoint mockado e praticar payload versionado.

### Requisição

```http
POST https://reqsys-api.fly.dev/api/requisitos
Content-Type: application/json
```

### Payload padrão ouro mínimo

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

### Estrutura recomendada no Power Automate

| Etapa | Ação | Observação |
|---|---|---|
| 1 | Manual trigger ou Forms | Capturar dados do requisito |
| 2 | Compose payload | Montar JSON versionado |
| 3 | HTTP POST | Enviar para `/api/requisitos` |
| 4 | Parse JSON | Ler resposta criada |
| 5 | Condition | Tratar sucesso ou erro |
| 6 | Log operacional | Guardar `correlation_id` |

## Campos obrigatórios

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---:|---|
| `titulo` | string | Sim | `Registrar requisito via Power Automate` |
| `descricao` | string | Sim | `Fluxo POST para praticar estrutura de dados.` |
| `tipo` | enum | Sim | `funcional` |
| `prioridade` | enum | Sim | `media` |
| `origem` | string | Sim | `power_automate` |
| `metadata.versao_contrato` | string | Recomendado | `0.3.0` |
| `metadata.correlation_id` | string | Recomendado | `power-automate-0001` |

## Regras de validação

- `tipo` deve ser um dos valores: `funcional`, `nao_funcional`, `regra_negocio`, `restricao`.
- `prioridade` deve ser um dos valores: `baixa`, `media`, `alta`, `critica`.
- `correlation_id` deve acompanhar logs e troubleshooting.
- Alterações de contrato devem gerar nova versão do OpenAPI.

## Artefato relacionado

```text
docs-site/assets/openapi/reqsys-runtime-openapi-v0.3.0.json
```
