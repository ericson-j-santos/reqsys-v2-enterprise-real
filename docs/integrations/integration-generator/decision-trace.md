# Decision Trace — excel_sql_sharepoint_sync

## Decisão

Implementar a demanda como primeiro caso de uso de um gerador de integrações orientado a contrato no ReqSys, em vez de criar um fluxo isolado.

## Razões

- reutilização para novos pares de origem/destino;
- validação centralizada de contratos;
- geração consistente de artefatos;
- governança e rastreabilidade por `correlation_id`;
- idempotência como requisito obrigatório;
- capacidade de validar E2E por perfil.

## Não objetivos deste incremento

- provisionar credenciais Microsoft ou SQL;
- executar contra produção;
- substituir a consulta SQL real sem fornecimento do contrato de negócio;
- declarar integração funcionalmente concluída sem E2E real em DEV.
