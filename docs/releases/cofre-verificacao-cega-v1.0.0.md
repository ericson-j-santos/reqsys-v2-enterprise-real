# Release Note — Cofre Verificação Cega v1.0.0

## Objetivo

Adicionar uma capacidade segura para comparar valores contra segredos armazenados no cofre sem retornar segredo bruto.

## Entregas

| Área | Entrega |
|---|---|
| Backend | Novo módulo `backend/app/core/cofre_verificador_cego.py` |
| API | Novo endpoint `POST /v1/cofre/verificar` |
| Segurança | Comparação constante para `X-Vault-Token` |
| Segurança | Chave operacional `REQSYS_COFRE_VERIFICADOR_PEPPER` bloqueada em endpoints de leitura |
| Testes | Testes unitários do verificador cego |
| Testes | Testes de API para match verdadeiro/falso e não exposição de valor |
| Governança | ADR e runbook versionados |
| Configuração | `.env.example` documentado |

## Contrato seguro

A API retorna somente:

```json
{
  "match": true,
  "verifier_version": "cego-v1",
  "value_exposed": false
}
```

A API não retorna:

- segredo bruto;
- digest;
- hash;
- fingerprint;
- valor operacional do verificador.

## Validação

```bash
cd backend
python -m pytest tests/test_cofre_verificador_cego.py tests/test_cofre_verificacao_api.py -v
```

## Pendências antes de produção

- Configurar `REQSYS_COFRE_VERIFICADOR_PEPPER` real por ambiente.
- Validar CI completo.
- Revisar logs para garantir ausência de valor candidato e segredo.
- Manter PR em draft até revisão e autorização explícita.
