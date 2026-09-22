# Tarefas — ReqSys Report Factory RDL/Fabric MVP

- [x] Registrar issue de consolidação #1933.
- [x] Definir ReportSpec 1.0 e JSON Schema.
- [x] Implementar validador fail-closed e gerador RDL determinístico.
- [x] Implementar `PaginatedReportDefinition` em Base64 e cliente Fabric create/update.
- [x] Criar exemplo, testes e runbook.
- [x] PR #1939 integrada.
- [x] Executar preflight OIDC no HEAD `3b8660844c446eedd63b461a776c9889360865cb`: tenant correto, token Fabric obtido, Fabric HTTP 200, zero workspaces visíveis à identidade CCP.
- [x] Executar descoberta independente no Noteri: workflow `Fabric HML Authorization Probe` run `35733911595`, workspace `ReqSys - Observabilidade` único e `ReqSys ALM Pipeline` com role `Contributor`, sem exposição de identificadores/segredos.
- [x] Concluir que não é necessário criar workspace nem conceder novo role Fabric.
- [x] Adicionar preflight somente leitura da FIC `reqsys-report-factory-development` no Noteri.
- [ ] Executar preflight FIC no HEAD exato e registrar `fic_ready`.
- [ ] Se `fic_ready=false`, criar somente a FIC faltante por fluxo Entra governado e revalidar por GET independente.
- [ ] Autenticar GitHub Actions como `ReqSys ALM Pipeline` via OIDC e comprovar visibilidade do workspace DEV.
- [ ] Executar E2E real de publicação e `getDefinition` no Fabric DEV.
- [ ] Adicionar exportação PDF/XLSX em incremento posterior.
- [ ] Adicionar chart/matrix em incremento posterior.
