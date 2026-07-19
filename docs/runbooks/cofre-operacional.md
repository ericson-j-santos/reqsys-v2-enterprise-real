# Runbook — Cofre de Segredos ReqSys

Data de referência: 2026-06-29

Operação do cofre local (AES-GCM + keyring) integrado ao backend FastAPI.

## Pré-requisitos

| Item | Valor |
| --- | --- |
| Backend | `uvicorn app.main:app` em `:8000` |
| Dependências | `keyring`, `cryptography` (em `requirements.txt`) |
| Admin JWT | Usuário com perfil admin (ex.: login demo) |
| Service token | `VAULT_API_TOKEN` no `.env` para lookup S2S |

## Inicialização (primeira vez)

```bash
# Via CLI local
python scripts/vault_setup.py init

# Via API (admin JWT)
curl -X POST http://127.0.0.1:8000/v1/cofre/init \
  -H "Authorization: Bearer <token_admin>"
```

## Operações comuns

### Gravar segredo

```bash
python scripts/vault_setup.py set JWT_SECRET "segredo-forte-min-32-chars"
```

Ou pela UI em `/segredos-status` → **Gravar segredo**.

### Ler segredo (script/CI)

```bash
export VAULT_API_TOKEN="<token>"
curl http://127.0.0.1:8000/v1/cofre/segredos/JWT_SECRET \
  -H "X-Vault-Token: $VAULT_API_TOKEN"
```

### Importar do `.env`

```bash
python scripts/vault_setup.py init
python scripts/vault_setup.py import-env
```

### Gerar token S2S global (legado)

```bash
python scripts/vault_setup.py gen-token
# Adicionar saída ao .env como VAULT_API_TOKEN=
```

> Prefira tokens escopados (abaixo) para qualquer consumidor novo — o `VAULT_API_TOKEN`
> global dá acesso a **todas** as chaves do cofre. Use-o só como fallback de transição.

### Criar token escopado por consumidor

```bash
curl -X POST http://127.0.0.1:8000/v1/cofre/tokens \
  -H "Authorization: Bearer <token_admin>" \
  -H "Content-Type: application/json" \
  -d '{"label": "projeto-externo-x", "key_patterns": ["PROJX_*"]}'
# {"token": "..."} — guarde agora, não é mostrado de novo
```

O token retornado só lê chaves que casem os `key_patterns` (glob). Listar (`GET /v1/cofre/tokens`,
não expõe o valor) e revogar (`DELETE /v1/cofre/tokens/{id}`) exigem JWT admin.

## Diagnóstico

| Endpoint | Auth | Retorno |
| --- | --- | --- |
| `GET /v1/cofre/status` | JWT admin | `inicializado`, `service`, `vault_api_token_configurado` |
| `GET /v1/sistema/segredos-status` | JWT qualquer | Origem por segredo (`env`, `vault`, `default`, `absent`) |

UI: menu **Governança → Segredos** (`/segredos-status`).

## Resolução de problemas

| Sintoma | Causa provável | Ação |
| --- | --- | --- |
| `Vault não inicializado` | Master key ausente | `POST /v1/cofre/init` ou `vault_setup.py init` |
| `503 VAULT_API_TOKEN não configurado` | Token S2S ausente | Definir `VAULT_API_TOKEN` no `.env` |
| `401 Vault token inválido` | Header errado | Usar `X-Vault-Token: <valor exato>` |
| Keyring indisponível (Linux headless) | Sem Secret Service | Usar env vars ou instalar `gnome-keyring`/`libsecret` |
| Todos ícones "não configurado" na UI | Campo `resolved` ausente na API | Atualizar backend (corrigido em ADR-041) |

## Segurança

- Chave `__master_key__` é bloqueada em todas as rotas de gestão/leitura.
- Valores nunca aparecem em `/v1/sistema/segredos-status`.
- Não commitar `.env`, tokens ou saída de `vault_setup.py get`.
- Em produção: `VAULT_API_TOKEN` com `secrets.token_urlsafe(32)` mínimo.
- Toda gravação/remoção/leitura de segredo gera `AuditoriaEvento` (chave e ação, nunca o valor) — consulte via `/v1/auditoria` filtrando `entidade=cofre_segredo`.
- Uso do token global legado em vez de um token escopado fica registrado como `COFRE_TOKEN_LEGADO_USADO` — útil para identificar quem ainda não migrou.
- `/api/v1/cofre/` tem rate limit dedicado no nginx (zona `cofre`, 5-10 req/s conforme ambiente).

## Testes

```bash
cd backend
python -m pytest tests/test_cofre_api.py tests/test_cofre_service.py -v
```

## Pendências relacionadas

- [Pendência manual — Teams v2 no Power Platform DEV](pendencia-teams-v2-powerplatform-dev.md):
  cadastro/revalidação de secrets do environment `reqsys-power-platform-dev` e
  criação do workflow de import ainda inexistente.

## Referências

- [ADR-041](../adr/ADR-041-cofre-segredos-locais.md)
- [CONTRACT_CATALOG](../padrao-ouro/CONTRACT_CATALOG.md)
- `scripts/vault_setup.py --help`
