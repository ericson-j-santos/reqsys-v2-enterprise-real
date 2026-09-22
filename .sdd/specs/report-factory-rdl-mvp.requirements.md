# Requisitos — ReqSys Report Factory RDL/Fabric MVP

## Contexto

O ReqSys já contém artefatos `.rdl/.rds` reais de DEV no domínio `movimento_email`. Este incremento **consolida** essa capacidade em um gerador reutilizável e não substitui nem altera relatórios produtivos existentes.

Issue: #1933  
Increment type: `consolidate`

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
- publicação real no Fabric DEV somente pode ser declarada validada após execução real e leitura independente da definição/artefato no mesmo SHA.

## Fora do escopo deste MVP

- gráficos e matrizes;
- credenciais SQL embutidas;
- publicação em STG/PROD;
- exportação PDF/XLSX como evidência de runtime;
- criação automática de workspace/capacity;
- armazenamento de segredos.
