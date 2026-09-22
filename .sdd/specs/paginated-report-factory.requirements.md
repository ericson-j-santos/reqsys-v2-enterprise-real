# Report Builder / Paginated Report Factory P0 — Requisitos

## Objetivo

Consolidar a LowCode Solution Factory do ReqSys com geração declarativa de relatórios paginados compatíveis com Power BI Report Builder / Microsoft Fabric, sem executar publicação externa neste incremento.

## Classificação

`consolidate`.

## Requisitos

1. O ReqSys deve expor um contrato declarativo para nome do relatório, título, consulta SQL, campos, parâmetros e orientação de página.
2. A geração deve produzir RDL XML no namespace `http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition`.
3. A mesma especificação deve produzir exatamente o mesmo RDL e o mesmo SHA-256, independentemente do `correlation_id` da execução.
4. O pacote deve produzir a definição `PaginatedReportDefinition` com o arquivo `<report_name>.rdl` em Base64 e `payloadType=InlineBase64`.
5. A consulta do relatório deve ser somente leitura: apenas `SELECT` ou CTE iniciada por `WITH`; comandos de escrita, DDL e `EXEC` devem falhar fechado.
6. Connection strings não podem aceitar senha, client secret ou access token inline.
7. O endpoint `POST /v1/hub-lowcode/reports/paginated/generate` deve gerar o artefato sem publicar, criar ou atualizar item no Fabric.
8. A resposta deve registrar `correlation_id`, `definition_sha256`, ambiente alvo e guardrails de governança.
9. Publicação no Fabric deve permanecer fora deste incremento e exigir autorização específica, identidade/credencial governada e E2E real no ambiente DEV.
10. Nenhum segredo deve ser registrado em código, teste, payload de evidência ou log.

## Controles negativos

- SQL destrutivo deve retornar erro de validação antes da geração.
- Connection string com segredo inline deve retornar erro de validação.
- `external_write_performed` deve permanecer `false`.
- O gerador não deve realizar chamada HTTP para Fabric ou Power BI.
- A especificação não deve depender de saída residual de execução anterior.

## Critérios de aceite

- `backend/tests/test_paginated_report_factory.py` verde no HEAD exato.
- O teste positivo decodifica o Base64, parseia o XML e confirma datasource, dataset, parâmetro e seção do relatório.
- O teste de idempotência comprova RDL e SHA-256 iguais para a mesma entrada repetida.
- Os testes negativos rejeitam SQL destrutivo e segredo inline.
- O teste de API comprova HTTP 200 no caso válido e HTTP 422 no controle negativo.
- SDD Gate verde para o HEAD final.
- Pre-PR Readiness retorna `READY_FOR_PR=passed` e `behind_by=0` antes da abertura da PR.
- A homologação real no Fabric permanece explicitamente pendente até publicação DEV autorizada e leitura/exportação independente do relatório gerado.
