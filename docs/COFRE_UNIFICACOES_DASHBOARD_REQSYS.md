# Cofre ReqSys — Implementação Canônica

Data: 2026-06-29 (atualizado)

## Localização atual

A implementação canônica do cofre está no backend FastAPI do ReqSys:

| Camada | Arquivo |
| --- | --- |
| API REST | `backend/app/api/cofre.py` |
| Serviço (AES-GCM + keyring) | `backend/app/core/secrets.py` |
| Diagnóstico | `backend/app/api/sistema.py` → `GET /v1/sistema/segredos-status` |
| CLI operacional | `scripts/vault_setup.py` |
| UI principal | `frontend/src/views/SegredosStatusView.vue` |
| Testes | `backend/tests/test_cofre_api.py`, `backend/tests/test_cofre_service.py` |

> A implementação legada em `codigoszipados_OLD/mvp intelligence/` foi substituída e não deve ser usada.

## Capacidades

- Armazenamento seguro com keyring + AES-256-GCM.
- Rotas REST para init, status, gravação, remoção e leitura service-to-service.
- Diagnóstico de origem dos segredos sem exposição de valores.
- Gestão integrada na tela `/segredos-status` (inicializar, gravar, remover).
- Fallback seguro quando keyring/cryptography indisponíveis (400/503, sem 500).

## Documentação Padrão Ouro

- [ADR-041 — Cofre de Segredos Locais](adr/ADR-041-cofre-segredos-locais.md)
- [Runbook operacional](runbooks/cofre-operacional.md)
- [Contract Catalog — Cofre](padrao-ouro/CONTRACT_CATALOG.md)

## Dashboard ReqSys

Fonte backend: `backend/app/api/dashboard.py`

Endpoints principais:

- `GET /v1/dashboard/requisitos`
- `GET /v1/dashboard/info`

O dashboard consome métricas de requisitos; o diagnóstico de segredos fica em `/segredos-status` (governança).
