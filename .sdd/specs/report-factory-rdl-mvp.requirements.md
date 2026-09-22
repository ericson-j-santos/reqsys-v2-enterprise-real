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
13. Antes de qualquer mutação Fabric DEV, reutilizar o GitHub Environment `development` e a identidade OIDC governada `CCP_AZURE_*` para executar probe somente leitura.
14. O preflight deve comprovar tenant esperado, obtenção de token temporário Fabric, HTTP 200 em `/v1/workspaces` e ao menos um workspace candidato, sem mutações.
15. Se o preflight comprovar que a identidade governada já possui acesso Fabric suficiente, preferir reutilizá-la em vez de criar outra App Registration sem necessidade.

## Critérios de aceite

- fluxo local `spec -> RDL -> Fabric payload` aprovado;
- RDL gerado contém datasource, dataset, parâmetro e Tablix declarados;
- Base64 do payload decodifica exatamente para o RDL gerado;
- controle negativo rejeita credenciais embutidas;
- controle negativo rejeita dataset inexistente;
- controle negativo rejeita componente ainda não suportado;
- duas execuções produzem RDL idêntico;
- testes `tests/test_report_factory_rdl.py` e `tests/test_report_factory_fabric_dev_preflight.py` verdes no HEAD exato;
- preflight Fabric DEV publica evidência sanitizada vinculada ao SHA;
- publicação real no Fabric DEV somente pode ser declarada validada após execução real e leitura independente da definição/artefato no mesmo SHA.

## Fora do escopo deste MVP

- gráficos e matrizes;
- credenciais SQL embutidas;
- publicação em STG/PROD;
- exportação PDF/XLSX como evidência de runtime;
- criação automática de workspace/capacity;
- armazenamento de segredos.
