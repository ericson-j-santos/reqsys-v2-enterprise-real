# Contrato Runtime — Connection Broker

## Objetivo

Definir os endpoints mínimos para transformar a decisão ADR-020 em capacidade executável no ReqSys.

---

## 1. Health-check de conectores

### `GET /api/connectors/health`

Retorna o estado operacional dos conectores e capabilities monitorados.

### Resposta esperada

```json
{
  "correlation_id": "reqsys-conn-20260620-0001",
  "data": {
    "correlation_id": "reqsys-conn-20260620-0001",
    "conectores": [
      {
        "ambiente": "homolog",
        "conector": "repository_provider",
        "capability": "repository.write",
        "status": "missing_permission",
        "criticidade": "critical",
        "acao_sugerida": "Solicitar autorização contextual antes da escrita."
      }
    ]
  }
}
```

### Status válidos

| Status | Significado |
|---|---|
| `ready` | Conector pronto para execução. |
| `missing_permission` | Permissão inexistente. |
| `insufficient_permission` | Permissão insuficiente para a capability. |
| `expired` | Autorização expirada. |
| `blocked` | Execução bloqueada por gate. |
| `unavailable` | Conector indisponível. |
| `misconfigured` | Configuração incompleta. |

---

## 2. Verificação de capability

### `POST /api/connectors/capabilities/check`

Valida se uma capability pode ser executada no ambiente informado.

### Requisição

```json
{
  "ambiente": "homolog",
  "capability": "repository.write",
  "acao": "abrir_pr",
  "correlation_id": "reqsys-conn-20260620-0002"
}
```

### Resposta liberada

```json
{
  "correlation_id": "reqsys-conn-20260620-0002",
  "data": {
    "allowed": true,
    "status": "ready",
    "requires_human_confirmation": true,
    "message": "Capability autorizada para execução governada."
  }
}
```

### Resposta bloqueada

```json
{
  "correlation_id": "reqsys-conn-20260620-0003",
  "data": {
    "allowed": false,
    "status": "missing_permission",
    "requires_human_confirmation": true,
    "message": "Solicitar autorização contextual antes de continuar."
  }
}
```

---

## 3. Regras de segurança

- Nunca retornar segredo, chave, token, refresh token, connection string ou credencial.
- Sempre retornar `correlation_id`.
- Bloquear produção quando capability crítica não tiver configuração válida.
- Preferir perfis de permissão em vez de nomes de escopos no payload público.
- Registrar auditoria fora do payload entregue ao frontend.

---

## 4. Integração frontend

A tela `/monitoramento-operacional` consome `GET /api/connectors/health`.

Enquanto o backend não estiver disponível, a tela usa fallback local sem credenciais, apenas para manter a experiência operacional e evidenciar o contrato esperado.

---

## 5. Testes mínimos

| Tipo | Critério |
|---|---|
| Unitário | Classificar corretamente cada status. |
| Contrato | Validar payload obrigatório dos endpoints. |
| Segurança | Garantir ausência de segredos no JSON de resposta. |
| E2E | Exibir cards e tabela de conectores em `/monitoramento-operacional`. |
| Governança | Bloquear capability crítica sem configuração válida. |
