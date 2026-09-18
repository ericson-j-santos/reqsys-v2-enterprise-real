# Aceite E2E — excel_sql_sharepoint_sync

## Pré-condições

- ambiente DEV identificado;
- branch e SHA registrados;
- tabela Excel de teste disponível;
- conectividade SQL Server funcional;
- lista SharePoint de teste disponível;
- `correlation_id` único por execução.

## Caso positivo

1. Inserir identificador válido e conhecido no Excel.
2. Executar o fluxo real.
3. Confirmar que o SQL processou o identificador da mesma execução.
4. Confirmar criação ou atualização do item no SharePoint.
5. Fazer leitura independente da lista e localizar o item pelo `correlation_id`/chave de negócio.

## Caso negativo

1. Inserir identificador fora do padrão numérico.
2. Executar o fluxo.
3. Confirmar que ele foi rejeitado ou colocado em quarentena antes da consulta de negócio.
4. Confirmar por leitura independente que nenhum item correspondente foi criado no SharePoint.

## Idempotência

1. Repetir exatamente a entrada válida da execução positiva.
2. Confirmar que o item existente foi atualizado, sem criação de duplicata.
3. Confirmar contagem única pela `ChaveIntegracao`.

## Controle contra falso positivo

A execução não é considerada aprovada apenas porque o workflow terminou verde, retornou HTTP 2xx ou escreveu log de sucesso. O estado persistido no SharePoint deve ser lido por uma operação independente e vinculado ao SHA e `correlation_id` correntes.
