# Gerador de Integrações do ReqSys

Este diretório contém contratos e documentação de perfis reutilizáveis de integração.

## Primeiro perfil

`excel_sql_sharepoint_sync`

Objetivo: ler identificadores de uma tabela Excel, consultar SQL Server por JSON parametrizado e aplicar upsert idempotente em uma lista SharePoint.

## Regra de evolução

Novos perfis devem reutilizar o mesmo núcleo de validação, geração, rastreabilidade e validação E2E. Integrações reais só podem ser declaradas concluídas após validação ponta a ponta no ambiente alvo com leitura independente do efeito final.
