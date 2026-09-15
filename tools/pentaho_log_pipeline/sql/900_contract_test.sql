SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRANSACTION;
BEGIN TRY
    DECLARE @LoteId uniqueidentifier = 'AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAA0914';
    DECLARE @Agora datetime2(0) = '2099-09-14T09:00:00';
    DECLARE @E1 uniqueidentifier = '11111111-1111-1111-1111-111111111111';
    DECLARE @E2 uniqueidentifier = '22222222-2222-2222-2222-222222222222';
    DECLARE @E3 uniqueidentifier = '33333333-3333-3333-3333-333333333333';
    DECLARE @E4 uniqueidentifier = '44444444-4444-4444-4444-444444444444';

    DECLARE @Payload nvarchar(max) = N'[
      {"execucao_id":"11111111-1111-1111-1111-111111111111","correlation_id":"91111111-1111-1111-1111-111111111111","processo":"TESTE_PENTAHO_1","execution_key":"exec-1","idempotency_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1","iniciado_em":"2026-09-14T08:50:00","finalizado_em":"2026-09-14T08:51:00","exit_code":0,"estado_execucao":"SUCESSO","log_caminho":"/var/log/pentaho/raw/1.log","log_sha256":"1111111111111111111111111111111111111111111111111111111111111111","tamanho_bytes":10,"host":"teste"},
      {"execucao_id":"22222222-2222-2222-2222-222222222222","correlation_id":"92222222-2222-2222-2222-222222222222","processo":"TESTE_PENTAHO_2","execution_key":"exec-2","idempotency_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2","iniciado_em":"2026-09-14T08:52:00","finalizado_em":"2026-09-14T08:53:00","exit_code":1,"estado_execucao":"FALHA","log_caminho":"/var/log/pentaho/raw/2.log","log_sha256":"2222222222222222222222222222222222222222222222222222222222222222","tamanho_bytes":20,"host":"teste"},
      {"execucao_id":"33333333-3333-3333-3333-333333333333","correlation_id":"93333333-3333-3333-3333-333333333333","processo":"TESTE_PENTAHO_3","execution_key":"exec-3","idempotency_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa3","iniciado_em":"2026-09-14T08:54:00","finalizado_em":"2026-09-14T08:55:00","exit_code":0,"estado_execucao":"SUCESSO","log_caminho":"/var/log/pentaho/raw/3.log","log_sha256":"3333333333333333333333333333333333333333333333333333333333333333","tamanho_bytes":30,"host":"teste"},
      {"execucao_id":"44444444-4444-4444-4444-444444444444","correlation_id":"94444444-4444-4444-4444-444444444444","processo":"TESTE_PENTAHO_4","execution_key":"exec-4","idempotency_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa4","iniciado_em":"2026-09-14T08:56:00","finalizado_em":"2026-09-14T08:57:00","exit_code":0,"estado_execucao":"SUCESSO","log_caminho":"/var/log/pentaho/raw/4.log","log_sha256":"4444444444444444444444444444444444444444444444444444444444444444","tamanho_bytes":40,"host":"teste"},
      {"execucao_id":"EXECUCAO-INVALIDA","correlation_id":"95555555-5555-5555-5555-555555555555","processo":"TESTE_PENTAHO_INVALIDO","execution_key":"exec-5","idempotency_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa5","iniciado_em":"2026-09-14T08:58:00","finalizado_em":"2026-09-14T08:59:00","exit_code":0,"estado_execucao":"SUCESSO","log_caminho":"/var/log/pentaho/raw/5.log","log_sha256":"5555555555555555555555555555555555555555555555555555555555555555","tamanho_bytes":50,"host":"teste"}
    ]';

    DECLARE @Carga1 TABLE (inseridos int, quarentenados int);
    DECLARE @Carga2 TABLE (inseridos int, quarentenados int);
    INSERT INTO @Carga1 EXEC dbo.sp_pentaho_log_ingestir_json @LoteId, @Payload;
    INSERT INTO @Carga2 EXEC dbo.sp_pentaho_log_ingestir_json @LoteId, @Payload;

    IF NOT EXISTS (SELECT 1 FROM @Carga1 WHERE inseridos = 4 AND quarentenados = 1)
        THROW 51901, 'Carga inicial divergente.', 1;
    IF NOT EXISTS (SELECT 1 FROM @Carga2 WHERE inseridos = 0 AND quarentenados = 0)
        THROW 51902, 'Reenvio do lote nao foi idempotente.', 1;
    IF (SELECT COUNT(*) FROM dbo.pentaho_log_quarentena WHERE lote_id = @LoteId) <> 1
        THROW 51903, 'Quarentena divergente.', 1;

    UPDATE dbo.pentaho_log_fila
       SET estado='AGUARDANDO', tentativas=0,
           disponivel_em=DATEADD(MINUTE,-10,@Agora), bloqueio_ate=NULL, consumidor=NULL
     WHERE execucao_id=@E1;
    UPDATE dbo.pentaho_log_fila
       SET estado='FALHA', tentativas=1,
           disponivel_em=DATEADD(MINUTE,-2,@Agora), bloqueio_ate=NULL, consumidor=NULL
     WHERE execucao_id=@E2;
    UPDATE dbo.pentaho_log_fila
       SET estado='PROCESSANDO', tentativas=1,
           disponivel_em=DATEADD(HOUR,-1,@Agora), bloqueio_ate=DATEADD(MINUTE,-5,@Agora),
           consumidor=N'consumidor-abandonado'
     WHERE execucao_id=@E3;
    UPDATE dbo.pentaho_log_fila
       SET estado='PROCESSANDO', tentativas=1,
           disponivel_em=DATEADD(HOUR,-1,@Agora), bloqueio_ate=DATEADD(MINUTE,30,@Agora),
           consumidor=N'consumidor-ativo'
     WHERE execucao_id=@E4;

    DECLARE @R TABLE
    (
        fila_id uniqueidentifier, execucao_id uniqueidentifier,
        correlation_id uniqueidentifier, processo nvarchar(200),
        iniciado_em datetime2(0), log_caminho nvarchar(2048),
        log_sha256 char(64), tamanho_bytes bigint,
        tentativa tinyint, bloqueio_ate datetime2(0)
    );
    INSERT INTO @R EXEC dbo.sp_pentaho_log_reservar
        @consumidor=N'contract-test', @quantidade=3, @lease_segundos=300, @agora=@Agora;

    IF (SELECT COUNT(*) FROM @R) <> 3
        THROW 51904, 'Reserva inicial deve conter tres itens.', 1;
    IF NOT EXISTS (SELECT 1 FROM @R WHERE execucao_id=@E1 AND tentativa=1)
        THROW 51905, 'Aguardando nao foi reservado.', 1;
    IF NOT EXISTS (SELECT 1 FROM @R WHERE execucao_id=@E2 AND tentativa=2)
        THROW 51906, 'Falha nao foi reprocessada.', 1;
    IF NOT EXISTS (SELECT 1 FROM @R WHERE execucao_id=@E3 AND tentativa=2)
        THROW 51907, 'Lease expirado nao foi recuperado.', 1;
    IF EXISTS (SELECT 1 FROM @R WHERE execucao_id=@E4)
        THROW 51908, 'Lease vigente foi reservado indevidamente.', 1;

    DECLARE @F1 uniqueidentifier=(SELECT fila_id FROM @R WHERE execucao_id=@E1);
    DECLARE @F2 uniqueidentifier=(SELECT fila_id FROM @R WHERE execucao_id=@E2);
    DECLARE @F3 uniqueidentifier=(SELECT fila_id FROM @R WHERE execucao_id=@E3);

    EXEC dbo.sp_pentaho_log_concluir @fila_id=@F1, @consumidor=N'contract-test',
        @arquivo_destino=N'/archive/1.log', @retencao_dias=30, @agora=@Agora;
    EXEC dbo.sp_pentaho_log_concluir @fila_id=@F3, @consumidor=N'contract-test',
        @arquivo_destino=N'/archive/3.log', @retencao_dias=30, @agora=@Agora;

    DECLARE @Falha2 TABLE (estado varchar(20), tentativas tinyint);
    INSERT INTO @Falha2 EXEC dbo.sp_pentaho_log_falhar
        @fila_id=@F2, @consumidor=N'contract-test', @erro=N'falha simulada',
        @retry_segundos=120, @agora=@Agora;
    IF NOT EXISTS (SELECT 1 FROM @Falha2 WHERE estado='FALHA' AND tentativas=2)
        THROW 51909, 'Segunda tentativa deveria permanecer reprocessavel.', 1;

    DECLARE @T903 datetime2(0)=DATEADD(MINUTE,3,@Agora);
    DECLARE @R2 TABLE
    (
        fila_id uniqueidentifier, execucao_id uniqueidentifier,
        correlation_id uniqueidentifier, processo nvarchar(200),
        iniciado_em datetime2(0), log_caminho nvarchar(2048),
        log_sha256 char(64), tamanho_bytes bigint,
        tentativa tinyint, bloqueio_ate datetime2(0)
    );
    INSERT INTO @R2 EXEC dbo.sp_pentaho_log_reservar
        @consumidor=N'contract-retry', @quantidade=3, @lease_segundos=300, @agora=@T903;
    IF (SELECT COUNT(*) FROM @R2) <> 1 OR
       NOT EXISTS (SELECT 1 FROM @R2 WHERE execucao_id=@E2 AND tentativa=3)
        THROW 51910, 'Terceira tentativa divergente.', 1;

    DECLARE @Falha3 TABLE (estado varchar(20), tentativas tinyint);
    INSERT INTO @Falha3 EXEC dbo.sp_pentaho_log_falhar
        @fila_id=@F2, @consumidor=N'contract-retry', @erro=N'terceira falha',
        @retry_segundos=120, @agora=@T903;
    IF NOT EXISTS (SELECT 1 FROM @Falha3 WHERE estado='DLQ' AND tentativas=3)
        THROW 51911, 'Terceira falha deveria ir para DLQ.', 1;

    DECLARE @T910 datetime2(0)=DATEADD(MINUTE,10,@Agora);
    DECLARE @R3 TABLE
    (
        fila_id uniqueidentifier, execucao_id uniqueidentifier,
        correlation_id uniqueidentifier, processo nvarchar(200),
        iniciado_em datetime2(0), log_caminho nvarchar(2048),
        log_sha256 char(64), tamanho_bytes bigint,
        tentativa tinyint, bloqueio_ate datetime2(0)
    );
    INSERT INTO @R3 EXEC dbo.sp_pentaho_log_reservar
        @consumidor=N'contract-after-dlq', @quantidade=3, @lease_segundos=300, @agora=@T910;
    IF (SELECT COUNT(*) FROM @R3) <> 0
        THROW 51912, 'DLQ ou lease vigente voltaram a ser elegiveis.', 1;

    DECLARE @T931 datetime2(0)=DATEADD(MINUTE,31,@Agora);
    DECLARE @R4 TABLE
    (
        fila_id uniqueidentifier, execucao_id uniqueidentifier,
        correlation_id uniqueidentifier, processo nvarchar(200),
        iniciado_em datetime2(0), log_caminho nvarchar(2048),
        log_sha256 char(64), tamanho_bytes bigint,
        tentativa tinyint, bloqueio_ate datetime2(0)
    );
    INSERT INTO @R4 EXEC dbo.sp_pentaho_log_reservar
        @consumidor=N'contract-recovery', @quantidade=3, @lease_segundos=300, @agora=@T931;
    IF (SELECT COUNT(*) FROM @R4) <> 1 OR
       NOT EXISTS (SELECT 1 FROM @R4 WHERE execucao_id=@E4 AND tentativa=2)
        THROW 51913, 'Lease vigente nao foi recuperado apos expirar.', 1;

    IF NOT EXISTS
    (
        SELECT 1 FROM dbo.pentaho_log_fila
        WHERE execucao_id=@E2 AND estado='DLQ' AND tentativas=3
    )
        THROW 51914, 'Estado persistido da DLQ divergente.', 1;

    SELECT 'PASS' AS contract_test,
           (SELECT inseridos FROM @Carga1) AS carga1_inseridos,
           (SELECT quarentenados FROM @Carga1) AS carga1_quarentenados,
           (SELECT inseridos FROM @Carga2) AS carga2_inseridos,
           (SELECT quarentenados FROM @Carga2) AS carga2_quarentenados,
           (SELECT COUNT(*) FROM @R) AS reservas_iniciais,
           (SELECT COUNT(*) FROM @R2) AS retry_terceira_tentativa,
           (SELECT COUNT(*) FROM dbo.pentaho_log_fila WHERE estado='DLQ' AND tentativas=3) AS dlq,
           (SELECT COUNT(*) FROM @R4) AS lease_recuperado;

    ROLLBACK TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
