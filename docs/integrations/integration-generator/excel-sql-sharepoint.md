# Gerador de Integrações — Excel → SQL Server → SharePoint

Status: incremento inicial

## Objetivo

Transformar a demanda Excel → SQL Server → SharePoint no primeiro perfil reutilizável do gerador de integrações do ReqSys.

## Contrato do perfil

```yaml
profile: excel_sql_sharepoint_sync
source:
  type: excel
  table: tbEntrada
  identifier_column: Identificador
  identifier_pattern: '^\\d+$'
sql:
  procedure: integration.usp_ConsultarPorIdentificadores
  input_mode: json
  key_field: Identificador
destination:
  type: sharepoint
  list: ResultadoConsulta
  business_key: ChaveIntegracao
  operation: upsert
governance:
  deduplicate: true
  correlation_id: true
  idempotent: true
  quarantine_invalid_rows: true
```

## Fluxo alvo

1. Ler apenas a coluna de identificação da tabela Excel.
2. Validar o padrão numérico.
3. Remover vazios e duplicidades.
4. Enviar a lista ao SQL Server como JSON parametrizado.
5. Converter os identificadores com `OPENJSON` na stored procedure.
6. Executar a consulta de negócio complexa.
7. Mapear o resultado para a lista SharePoint.
8. Criar ou atualizar pelo campo `ChaveIntegracao`.
9. Propagar `correlation_id` em toda a execução.
10. Validar o efeito final por leitura independente do SharePoint.
11. Reexecutar a mesma entrada para comprovar idempotência.

## Critérios de aceite do incremento completo

- identificador válido chega ao SQL;
- identificador inválido é rejeitado antes da consulta de negócio;
- duplicados do Excel são processados uma única vez;
- registro inexistente é criado no SharePoint;
- registro existente é atualizado sem duplicação;
- reprocessamento da mesma entrada não cria duplicatas;
- evidências da execução estão vinculadas ao mesmo `correlation_id`, ambiente, branch e SHA;
- E2E real executado em DEV com caso positivo, negativo e leitura independente do destino.

## Limites deste incremento

Este primeiro incremento estabelece o contrato e a direção arquitetural. Provisionamento Microsoft 365, credenciais, gateway SQL e validação real em DEV serão adicionados em incrementos subsequentes e não devem ser declarados concluídos sem evidência ponta a ponta.
