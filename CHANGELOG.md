# Changelog

All notable changes to this project are documented in this file.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) — [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [Unreleased] - 2026-06-20

### Adicionado

- Diretriz transversal de padrão ouro em `docs/REQSYS_PADRAO_OURO_TRANSVERSAL.md`.
- Varredura técnica inicial em `docs/varreduras/REQSYS_VARREDURA_PADRAO_OURO_2026-06-20.md`.
- Helper puro `frontend/src/utils/filtrosRequisitos.js` para normalização, query string e filtragem analítica de requisitos.
- Teste unitário `frontend/src/utils/filtrosRequisitos.test.js` para filtros analíticos de requisitos.
- Script `npm run test:unit` no frontend.

### Alterado

- `DashboardView.vue`: cards de requisitos agora apontam para rotas analíticas com filtros por query string quando aplicável.
- `DashboardView.vue`: melhoria de acessibilidade por teclado nos cards interativos.
- `RequisitosView.vue`: adicionados filtros analíticos por status, urgência, área e busca textual.
- `RequisitosView.vue`: leitura e preservação de query string para abertura de analítico filtrado a partir do dashboard.
- `RequisitosView.vue`: total filtrado, estado visual de filtro ativo, alerta de lista vazia e botão para limpar filtros.

### Validação pendente

- Executar `npm run test:unit` em ambiente local ou CI.
- Executar `npm run build` no frontend.
- Validar visualmente desktop, tablet e mobile.

### Ambiente

- Ambiente observado: GitHub / branch `main`.
- Ambiente de aplicação: branch `docs/padrao-ouro-transversal-reqsys`.
- Produção: sem alteração direta.

---

## [3.1.0] - 2026-05-28

### Adicionado

- Versionamento canônico em `VERSION` antes do desenvolvimento da nova aplicação.
- Documentação GitFlow em `docs/GITFLOW.md`, com branches, checklist de release, convenção de commits e fluxo de tag.
- Aplicação inicial completa em .NET 8/C# em `backend-dotnet/`, com solution, projeto ASP.NET Core Minimal API, Dockerfile, README e testes xUnit.
- Módulos .NET entregues: autenticação, saúde, sistema, dashboard, requisitos CRUD, pipeline, relatórios, auditoria e qualidade IA.

### Alterado

- README atualizado para declarar a versão `3.1.0` e a nova stack .NET/C# em evolução.
- API FastAPI existente alinhada para versão `3.1.0` e compatibilidade dos testes de autenticação/diagnóstico de segredos.
- Metadados de versão dos assemblies .NET centralizados em `backend-dotnet/Directory.Build.props`.
- `.gitignore` atualizado para ignorar banco local de testes na raiz e permitir rastrear a solution .NET em `backend-dotnet/`.

### Testado

- Conferência estática dos artefatos C# criados e dos arquivos de versionamento.
- Teste automatizado .NET documentado em `backend-dotnet/tests/ReqSys.Api.Tests`; execução local bloqueada no ambiente atual porque o SDK `dotnet` não está instalado.

### Rollback

- Remover o diretório `backend-dotnet/`, reverter `VERSION`, `README.md`, `CHANGELOG.md` e `docs/GITFLOW.md` para retornar ao backend FastAPI como única implementação ativa.
