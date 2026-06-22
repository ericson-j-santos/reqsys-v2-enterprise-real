# Runbook — Verificação cega do cofre

## Objetivo

Validar se um valor informado é igual a um valor armazenado no cofre sem retornar o segredo bruto, sem retornar digest e sem expor fingerprint.

## Endpoint recomendado

```http
POST /v1/cofre/verificar
X-Vault-Token: <VAULT_API_TOKEN>
Content-Type: application/json
```

Payload:

```json
{
  "key": "NOME_DA_CHAVE",
  "value": "valor-candidato"
}
```

Resposta:

```json
{
  "success": true,
  "data": {
    "key": "NOME_DA_CHAVE",
    "match": true,
    "verifier_version": "cego-v1",
    "value_exposed": false
  }
}
```

## Preparação do valor operacional

1. Inicializar o cofre por ambiente.
2. Gerar valor forte com pelo menos 32 bytes.
3. Gravar no cofre com a chave `REQSYS_COFRE_VERIFICADOR_PEPPER`.
4. Nunca resolver esta chave por endpoint de leitura.

Exemplo de geração local:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Guardrails

- `POST /v1/cofre/verificar` retorna apenas verdadeiro/falso.
- `REQSYS_COFRE_VERIFICADOR_PEPPER` não pode ser consultado por `/resolver` ou `/segredos/{key}`.
- A comparação do token do cofre usa comparação constante.
- A resposta não contém `value`, `digest`, `hash` ou `fingerprint`.
- O valor operacional fraco ou ausente retorna `503`.

## Validação local

```bash
cd backend
python -m pytest tests/test_cofre_verificador_cego.py tests/test_cofre_verificacao_api.py -v
```

## Critério de pronto

- Testes novos verdes.
- CI completo verde.
- PR em draft até revisão concluída.
- Sem alteração que relaxe gates de produção.
- Sem logs contendo valor candidato, segredo do cofre ou valor operacional.
