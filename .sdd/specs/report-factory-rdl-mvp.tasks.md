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
- [x] Adicionar e executar preflight somente leitura da FIC no Noteri.
- [x] Run `35736166631`, HEAD `d2e54a92fea1104afffaf4711bbde6961d6b51d2`: app/workspace únicos, `Contributor`, `fic_list_status=200`, `fic_exact_count=0`, `fic_ready=false`, nenhuma mutação/exposição.
- [x] Adicionar bootstrap idempotente da única FIC faltante, limitado a `ReqSys ALM Pipeline`, Environment `development`, `workflow_dispatch` e confirmação literal.
- [x] Corrigir contrato da PR #1950: instalar `pytest` no job Ubuntu e registrar os workflows FIC na allowlist self-hosted com teste explícito.
- [ ] Revalidar contrato/Pre-PR do bootstrap no HEAD exato.
- [ ] Executar o bootstrap em modo `apply` somente após autorização explícita para a mutação Entra.
- [ ] Revalidar por GET independente: `fic_exact_count=1` e `fic_ready=true`.
- [x] Conceder `Contributor` à identidade OIDC governada atual no workspace DEV: run `35735255608`, `write_status=201`, pós-condição `after_roles=['Contributor']`.
- [x] Revalidar pela própria identidade OIDC: run `35735423579`, Fabric HTTP 200 e `fabric_workspace_count=1` para `ReqSys - Observabilidade`.
- [ ] Concluir a FIC de `ReqSys ALM Pipeline` como migração/hardening separado; não bloquear o E2E atual já autenticado pela identidade OIDC governada.
- [x] Implementar modo governado `publish-e2e` no workflow existente, sem aumentar a superfície de workflows.
- [x] Adicionar comando exato do Authorized Actions Gateway e testes contratuais.
- [x] Executar E2E real no run `35845191652`: preflight aprovado, publicação bloqueada por `fabric_http_400`; causa raiz identificada como RDL 2016 parametrizado sem `ReportParametersLayout` obrigatório.
- [ ] Corrigir o gerador/validador RDL para materializar e exigir o layout de parâmetros antes de nova publicação.
- [x] Reexecutar E2E após PR #1988 no run `35846231809`: preflight aprovado e publicação ainda bloqueada por `fabric_http_400`, comprovando uma segunda causa ainda não distinguível pela evidência sanitizada atual.
- [x] Preservar na evidência somente códigos estruturados seguros retornados pelo Fabric, inclusive causas aninhadas, sem mensagens/IDs/tokens, para eliminar diagnóstico por tentativa.
- [ ] Reexecutar E2E real de publicação e `getDefinition` no Fabric DEV após merge do diagnóstico seguro.
- [ ] Repetir a mesma definição e comprovar idempotência/ausência de duplicidade na evidência do mesmo run.
- [ ] Adicionar exportação PDF/XLSX em incremento posterior.
- [ ] Adicionar chart/matrix em incremento posterior.

- [x] Reexecutar o E2E real após a correção de layout: run `35855595593` no SHA `e6a3821ce559d173524ac4dfc953f93fc715dff7`; preflight/OIDC/workspace aprovados e criação bloqueada por `fabric_http_400:InvalidDefinitionFormat`.
- [ ] Alinhar o cabeçalho RDL 2016 ao contrato público oficial do Fabric e reexecutar o E2E no SHA integrado.

- [x] Reexecutar E2E após a PR #1996: run `35866066425` na main, com OIDC/workspace aprovados e criação ainda bloqueada por `fabric_http_400:InvalidDefinitionFormat`, sem código aninhado adicional.
- [x] Implementar diagnóstico fail-closed que preserva somente nomes de elementos RDL allowlisted e coordenadas de esquema, descartando mensagens/URLs/IDs/tokens/valores arbitrários.
- [ ] Validar o diagnóstico no CI/Pre-PR do HEAD exato e reexecutar o E2E Fabric DEV após merge governado.
- [x] Reexecutar E2E pós-PR #2002 no run `35877440535`, `main@a81e7d81f91f98328d2a3e844b8a9c21856833ac`: preflight/OIDC/workspace aprovados, criação ainda bloqueada por `fabric_http_400:InvalidDefinitionFormat`, sem detalhe adicional retornado pelo Fabric.
- [x] Comparar a definição gerada com RDLs 2016 produzidos pelo Report Builder e identificar a ausência de `rd:SecurityType` e `rd:DataSourceID` no datasource SQL integrado.
- [x] Emitir e validar metadata determinística do datasource sem segredo estático.
- [ ] Reexecutar Pre-PR no HEAD exato, integrar por merge governado e repetir o E2E Fabric DEV.

