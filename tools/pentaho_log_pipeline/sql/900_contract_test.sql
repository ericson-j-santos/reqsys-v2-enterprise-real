SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRANSACTION;
BEGIN TRY
    DECLARE @LoteId uniqueidentifier = 'AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAA0914';
    DECLARE @Agora datetime2(0) = '2099-09-14T09:00:00';
    DECLARE @Payload nvarchar(max) = N'
    [
      {
        "execucao_id":"11111111-1111-1111-1111-111111111111",
        "correlation_id":"91111111-1111-1111-1111-111111111111",
        "processo":"TESTE_PENTAHO_1",
        "execution_key":"exec-1",
        "idempotency_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1",
        "iniciado_em":"2026-09-14T08:50:00",
        "finalizado_em":"2026-09-14T08:51:00",
        "exit_code":0,
        "estado_execucao":"SUCESSO",
        "log_caminho":"/var/log/pentaho/raw/1.log",
        "log_sha256":"1111111111111111111111111111111111111111111111111111111111111111",
        "tamanho_bytes":10,
        "host":"teste"
      },
      {
        "execucao_id":"22222222-2222-2222-2222-222222222222",
        "correlation_id":"92222222-2222-2222-2222-222222222222",
        "processo":"TESTE_PENTAHO_2",
        "execution_key":"exec-2",
        "idempotency_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2",
        "iniciado_em":"2026-09-14T08:52:00",
        "finalizado_em":"2026-09-14T08:53:00",
        "exit_code":1,
        "estado_execucao":"FALHA",
        "log_caminho":"/var/log/pentaho/raw/2.log",
        "log_sha256":"2222222222222222222222222222222222222222222222222222222222222222",
        "tamanho_bytes":20,
        "host":"teste"
      },
      {
        "execucao_id":"33333333-3333-3333-3333-333333333333",
        "correlation_id":"93333333-3333-3333-3333-333333333333",
        "processo":"TESTE_PENTAHO_3",
        "execution_key":"exec-3",
        "idempotency_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa3",
        "iniciado_em":"2026-09-14T08:54:00",
        "finalizado_em":"2026-09-14T08:55:00",
        "exit_code":0,
        "estado_execucao":"SUCESSO",
        "log_caminho":"/var/log/pentaho/raw/3.log",
        "log_sha256":"3333333333333333333333333333333333333333333333333333333333333333",
        "tamanho_bytes":30,
        "host":"teste"
      },
      {
        "execucao_id":"44444444-4444-4444-4444-444444444444",
        "correlation_id":"94444444-4444-4444-4444-444444444444",
        "processo":"TESTE_PENTAHO_4",
        "execution_key":"exec-4",
        "idempotency_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa4",
        "iniciado_em":"2026-09-14T08:56:00",
        "finalizado_em":"2026-09-14T08:57:00",
        "exit_code":0,
        "estado_execucao":"SUCESSO",
        "log_caminho":"/var/log/pentaho/raw/4.log",
        "log_sha256":"4444444444444444444444444444444444444444444444444444444444444444",
        "tamanho_bytes":40,
        "host":"teste"
      },
      {
        "execucao_id":"EXECUCAO-INVALIDA",
        "correlation_id":"95555555-5555-5555-5555-555555555555",
        "processo":"TESTE_PENTAHO_INVALIDO",
        "execution_key":"exec-5",
        "idempotency_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5",
        "iniciado_em":"2026-09-14T08:58:00",
        "finalizado_em":"2026-09-14T08:59:00",
        "exit_code":0,
        "estado_execucao":"SUCESSO",
        "log_caminho":"/var/log/pentaho/raw/5.log",
        "log_sha256":"5555555555555555555555555555555555555555555555555555555555555555",
        "tamanho_bytes":50,
        "host":"teste"
      }
    ]';

    DECLARE @Carga1 TABLE (inseridos int, quarentenados int);
    DECLARE @Carga2 TABLE (inseridos int, quarentenados int);

    INSERT INTO @Carga1 EXEC dbo.sp_pentaho_log_ingestir_json @LoteId, @Payload;
    INSERT INTO @Carga2 EXEC dbo.sp_pentaho_log_ingestir_json @LoteId, @Payload;

    IF NOT EXISTS (SELECT 1 FROM @Carga1 WHERE inseridos = 4 AND quarentenados = 1)
        THROW 51901, 'Carga inicial nao produziu 4 inseridos e 1 quarentena.', 1;

    IF NOT EXISTS (SELECT 1 FROM @Carga2 WHERE inseridos = 0 AND quarentenados = 0)
        THROW 51902, 'Segunda carga nao foi idempotente.', 1;

    IF (SELECT COUNT(*) FROM dbo.pentaho_log_execucao WHERE processo LIKE 'TESTE_PENTAHO_%') <> 4
        THROW 51903, 'Quantidade de execucoes valida divergente.', 1;

    IF (SELECT COUNT(*) FROM dbo.pentaho_log_quarentena WHERE lote_id = @LoteId) <> 1
        THROW 51904, 'Quantidade de quarentena divergente.', 1;

    DECLARE @Reservados TABLE
    (
        fila_id uniqueidentifier,
        execucao_id uniqueidentifier,
        correlation_id uniqueidentifier,
        processo nvarchar(200),
        iniciado_em datetime2(0),
        log_caminho nvarchar(2048),
        log_sha256 char(64),
        tamanho_bytes bigint,
        tentativa tinyint,
        bloqueio_ate datetime2(0)
    );

    INSERT INTO @Reservados
    EXEC dbo.sp_pentaho_log_reservar
        @consumidor = N'contract-test',
        @quantidade = 3,
        @lease_segundos = 300,
        @agora = @Agora;

    IF (SELECT COUNT(*) FROM @Reservados) <> 3
        THROW 51905, 'Reserva nao retornou exatamente tres itens.', 1;

    IF EXISTS (SELECT 1 FROM @Reservados WHERE tentativa <> 1)
        THROW 51906, 'Primeira reserva deve registrar tentativa 1.', 1;

    IF (SELECT COUNT(*) FROM dbo.pentaho_log_fila WHERE estado = 'PROCESSANDO' AND consumidor = N'contract-test') <> 3
        THROW 51907, 'Estado persistido nao confirma as tres reservas.', 1;

    SELECT 'PASS' AS contract_test,
           (SELECT inseridos FROM @Carga1) AS carga1_inseridos,
           (SELECT quarentenados FROM @Carga1) AS carga1_quarentenados,
           (SELECT inseridos FROM @Carga2) AS carga2_inseridos,
           (SELECT quarentenados FROM @Carga2) AS carga2_quarentenados,
           (SELECT COUNT(*) FROM @Reservados) AS reservados;

    ROLLBACK TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
