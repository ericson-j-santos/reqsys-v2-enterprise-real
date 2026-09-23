# Requisitos — ReqSys Report Factory RDL/Fabric MVP

## Contexto

O ReqSys já contém artefatos `.rdl/.rds` reais de DEV no domínio `movimento_email`. Este incremento **consolida** essa capacidade em um gerador reutilizável e não substitui nem altera relatórios produtivos existentes.

Issue: #1933  
Increment type: `gap_fix`

## Requisitos funcionais

1. Receber uma especificação declarativa `ReportSpec` versão `1.0`.
2. Aceitar JSON como formato canônico e YAML quando `PyYAML` estiver disponível.
3. Validar nomes, datasets, fields, parâmetros e referências antes da geração.
4. Falhar fechado quando `connect_string` contiver senha, usuário, token ou client secret.
5. No MVP, aceitar somente datasource SQL com autenticação integrada.
6. No MVP, gerar componente `table` com cabeçalho e detalhe.
7. Gerar RDL no namespace `2016/01/reportdefinition`.
8. Produzir saída determinística: mesma especificação deve gerar os mesmos bytes.
9. Gerar `PaginatedReportDefinition` com RDL em Base64 e `payloadType=InlineBase64`.
10. Criar ou atualizar um relatório paginado no Fabric somente com identidade temporária autorizada em runtime; segredo estático não é requisito da arquitetura final.
11. Acompanhar operações `202 Accepted` por `Location` com timeout limitado.
12. Não registrar nem persistir token de acesso.
13. Antes de qualquer mutação Fabric DEV, executar descoberta somente leitura.
14. O probe OIDC governado deve comprovar tenant e token Fabric; HTTP 200 com zero workspaces é evidência válida de autenticação, mas não de autorização de workspace.
15. Reutilizar o workspace existente `ReqSys - Observabilidade` quando a descoberta independente comprovar unicidade e a App Registration `ReqSys ALM Pipeline` possuir `Contributor` ou superior.
16. Antes de criar qualquer Federated Identity Credential, executar preflight somente leitura no Noteri e comprovar se já existe exatamente uma FIC `reqsys-report-factory-development` para o subject `repo:ericson-j-santos/reqsys-v2-enterprise-real:environment:development`.
17. O preflight FIC não pode criar credencial, alterar RBAC, persistir token ou expor Application ID/Workspace ID.
18. Se a FIC já existir, reutilizá-la. Se estiver ausente, qualquer criação posterior deve ser idempotente, limitada à App Registration já autorizada e tratada como mutação Entra separada.
19. O `workflow_dispatch` do preflight deve permanecer somente leitura por padrão; publicação exige `mode=publish-e2e` explícito.
20. A publicação E2E DEV deve ser acionada pelo comando exato `/reqsys run report-factory-fabric-dev-e2e`, sem workspace, ambiente ou workflow arbitrários.
21. O E2E deve localizar exatamente um workspace `ReqSys - Observabilidade` e falhar fechado diante de ausência ou ambiguidade.
22. O E2E deve criar o relatório quando ausente ou atualizar sua definição quando existir, mantendo exatamente um item com o nome da `ReportSpec`.
23. Após a escrita, o E2E deve executar `getDefinition`, decodificar a parte `.rdl` e comparar SHA-256 com o RDL gerado no mesmo SHA.
24. O E2E deve repetir a mesma definição no mesmo item e comprovar ausência de duplicidade e igualdade do SHA-256 após o replay.
25. O fluxo não pode persistir token, criar segredo, aceitar STG/PROD nem declarar sucesso sem leitura independente da definição.
26. Quando houver `ReportParameters`, o RDL 2016 deve incluir `ReportParametersLayout` com `GridLayoutDefinition` e uma `CellDefinition` única para cada parâmetro, evitando payload estruturalmente inválido no Fabric.
27. Falhas HTTP do Fabric devem registrar somente o status HTTP e os códigos estruturados sanitizados (`errorCode`/`code`), inclusive causas aninhadas em objetos/listas, com limite de quantidade/tamanho; nunca corpo bruto, mensagem, token ou identificadores sensíveis.

## Critérios de aceite

- fluxo local `spec -> RDL -> Fabric payload` aprovado;
- RDL gerado contém datasource, dataset, parâmetro e Tablix declarados;
- Base64 do payload decodifica exatamente para o RDL gerado;
- controle negativo rejeita credenciais embutidas;
- controle negativo rejeita dataset inexistente;
- controle negativo rejeita componente ainda não suportado;
- duas execuções produzem RDL idêntico;
- testes do Report Factory e dos preflights verdes no HEAD exato;
- evidência OIDC atual registra `tenant_match=true`, token Fabric obtido e HTTP 200;
- evidência independente comprova exatamente um `ReqSys - Observabilidade` e `Contributor` para `ReqSys ALM Pipeline`;
- preflight FIC atual publica `fic_ready=true/false` sem mutação e sem identificadores;
- publicação real no Fabric DEV somente pode ser declarada validada após execução real e leitura independente da definição/artefato no mesmo SHA;
- execução governada `publish-e2e` deve comprovar `workspace_exact_count=1`, `final_report_exact_count=1`, `definition_verified=true` e `idempotency_verified=true`;
- o SHA-256 observado via `getDefinition` deve ser igual ao SHA-256 do RDL gerado na mesma execução.
- RDL parametrizado deve ser rejeitado localmente quando `ReportParametersLayout` estiver ausente ou não mapear exatamente os parâmetros declarados.
- erro HTTP do Fabric deve produzir evidência acionável como `fabric_http_400:<codigo>:<causa_aninhada>` quando houver códigos estruturados adicionais, sem incluir mensagens brutas, identificadores ou token.

## Fora do escopo deste MVP

- gráficos e matrizes;
- credenciais SQL embutidas;
- publicação em STG/PROD;
- exportação PDF/XLSX como evidência de runtime;
- criação automática de workspace/capacity;
- armazenamento de segredos.

28. O RDL 2016 destinado ao Fabric DEV deve emitir o cabeçalho compatível com a definição pública oficial do Fabric: `MustUnderstand=df`, `rd:ReportUnitType=Inch`, `rd:ReportID` UUID determinístico, `df:DefaultFontFamily=Segoe UI` e `AutoRefresh=0`; quando houver parâmetros, `ReportParametersLayout` deve permanecer após `ReportSections` no XML gerado.
