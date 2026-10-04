# Runbook — verificação cega do cofre

## Preparação

1. Inicialize o cofre.
2. Gere um valor aleatório com pelo menos 32 bytes de entropia adequada.
3. Grave-o no cofre com a chave `REQSYS_COFRE_VERIFICADOR_PEPPER`.
4. Não registre esse valor em `.env`, logs, documentação ou CI.

## Verificação

`POST /v1/cofre/verificar`

Payload:

```json
{"key":"MINHA_CHAVE","value":"valor-candidato"}
```

Autenticação: `X-Vault-Token` global legado ou token escopado que autorize `MINHA_CHAVE`.

A resposta contém somente:

- chave;
- `match`;
- versão do verificador;
- `value_exposed=false`.

## Falha fechada

- segredo alvo ausente: 404;
- chave operacional ausente/fraca: 503;
- chave operacional usada como alvo: bloqueada;
- token sem escopo: 403;
- token inválido: 401.

## Rotação

A chave operacional pode ser sobrescrita pela rota administrativa de gravação. Não existe leitura pela API.
