# ADR-041 — Cofre de Segredos Locais (AES-GCM + Keyring)

## Status

Aceito

## Contexto

O ReqSys precisa armazenar segredos (JWT, tokens de integração, credenciais Azure) sem expô-los em variáveis de ambiente em disco ou logs. Havia implementação legada no MVP Intelligence; o cofre foi consolidado no backend FastAPI principal com API REST e diagnóstico em `/segredos-status`.

## Decisão

Adotar cofre local com:

- **Criptografia**: AES-256-GCM com nonce de 12 bytes por segredo.
- **Armazenamento**: `keyring` do SO (Credential Manager no Windows, Secret Service no Linux).
- **Master key**: slot reservado `__master_key__` — nunca acessível via API.
- **Service name**: configurável via `REQSYS_VAULT_SERVICE_NAME` (default `mvp-intelligence-vault`).
- **API de gestão** (`/v1/cofre/*`): JWT admin obrigatório.
- **API de lookup** (`GET/POST /v1/cofre/segredos`, `/resolver`): header `X-Vault-Token` com `VAULT_API_TOKEN`.
- **Resolução híbrida**: `get_secret()` prioriza env por padrão; `prefer_vault=True` inverte.
- **Diagnóstico**: `GET /v1/sistema/segredos-status` retorna origem sem expor valores (`value_exposed: false`).

### Endpoints

| Método | Rota | Auth | Finalidade |
| --- | --- | --- | --- |
| `POST` | `/v1/cofre/init` | JWT admin | Cria master key |
| `GET` | `/v1/cofre/status` | JWT admin | Estado do cofre |
| `POST` | `/v1/cofre/segredos` | JWT admin | Grava segredo |
| `DELETE` | `/v1/cofre/segredos/{key}` | JWT admin | Remove segredo |
| `GET` | `/v1/cofre/segredos/{key}` | `X-Vault-Token` | Lê valor (service-to-service) |
| `POST` | `/v1/cofre/resolver` | `X-Vault-Token` | Alias POST de leitura |

### Frontend

Tela `/segredos-status` no frontend principal integra diagnóstico e gestão do cofre (inicializar, gravar, remover) — sem página externa `cofre.html`.

### CLI

`scripts/vault_setup.py` para operação local: `init`, `set`, `get`, `delete`, `status`, `import-env`, `gen-token`.

## Consequências positivas

- Segredos criptografados em repouso no keyring do SO.
- Lookup service-to-service para CI/CD (ex.: `configurar_fly_auth_azure.py`).
- Diagnóstico operacional sem vazamento de valores.
- 95+ testes automatizados cobrindo API e serviço.

## Consequências negativas / riscos

- Keyring indisponível em alguns containers Linux → vault retorna indisponível (503/400), não 500.
- `overwrite=true` em `/init` invalida todos os segredos existentes.
- Produção exige `VAULT_API_TOKEN` forte e `JWT` admin restrito.

## Gates

- Não expor valores de segredos em logs, auditoria ou respostas de diagnóstico.
- Alterações em cofre bloqueiam governed automerge (ADR-030).
- CI: `tests/test_cofre_api.py` + `tests/test_cofre_service.py` obrigatórios.

## Evidência

- `backend/app/api/cofre.py`, `backend/app/core/secrets.py`
- `frontend/src/views/SegredosStatusView.vue`
- `docs/runbooks/cofre-operacional.md`
- `docs/padrao-ouro/CONTRACT_CATALOG.md` — seção Cofre
