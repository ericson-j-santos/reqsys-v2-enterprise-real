# Cofre, Unificações e Dashboard ReqSys

Data: 2026-05-03

## Mapeamento da aplicação de cofre

A implementação de cofre está no projeto MVP Intelligence (fora do frontend do ReqSys), nos arquivos:

- `codigoszipados/mvp intelligence/mvp_intelligence/backend/services/vault.py`
- `codigoszipados/mvp intelligence/mvp_intelligence/backend/routers/vault_router.py`

### O que existe hoje no cofre

- Armazenamento seguro com keyring + AES-GCM.
- Rotas REST para status, listagem de chaves, gravação, remoção e verificação.
- Fallback seguro para ambiente sem backend de keyring funcional (retorna indisponível/503 sem erro 500).

## Unificações posteriores já registradas

Consolidação operacional entre ReqSys e MVP Intelligence já documentada em:

- `codigoszipados/mvp intelligence/mvp_intelligence/docs/STATUS_INTEGRADO_APLICACOES_2026-05-03.md`

Pontos consolidados:

- Domínios separados para cada aplicação.
- Validação de saúde das APIs e frontends.
- Comportamento esperado do vault em ambiente Linux/container.

## Informação do dashboard do ReqSys

Fonte backend do dashboard:

- `backend/app/api/dashboard.py`

Endpoints principais:

- `GET /v1/dashboard/requisitos`
- `GET /v1/dashboard/info`

Dados retornados:

- Métricas principais (total, em análise, aprovados, pendentes).
- Endpoints críticos para operação.
- Resumo do ambiente e status do sistema.
- Links de documentação e health-check.

## Melhorias aplicadas no dashboard do ReqSys

Arquivos atualizados:

- `frontend/src/views/DashboardView.vue`
- `frontend/src/stores/requisitos.js`
- `frontend/src/styles.css`
- `frontend/tests/e2e/dashboard.spec.js`

Melhorias entregues:

- Correções de acentuação e textos em PT-BR.
- Tooltips nas métricas e etapas do pipeline.
- Layout responsivo para cards e cabeçalho.
- Seção de informações do sistema alimentada por `/v1/dashboard/info`.
- Teste E2E do dashboard cobrindo conteúdo principal + tooltip + viewport mobile.

## Observação de validação

A execução local do teste E2E depende do ambiente em `http://reqsys.localtest.me:8082` estar ativo.
No momento do teste, o Docker local estava indisponível (daemon não iniciado), impedindo validação fim a fim automatizada nesse host.
