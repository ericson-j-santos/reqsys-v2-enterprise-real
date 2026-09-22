SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF OBJECT_ID('dbo.pentaho_log_execucao', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.pentaho_log_execucao
    (
        execucao_id       uniqueidentifier NOT NULL
            CONSTRAINT PK_pentaho_log_execucao PRIMARY KEY,
        correlation_id    uniqueidentifier NOT NULL,
        processo          nvarchar(200)     NOT NULL,
        execution_key     nvarchar(300)     NOT NULL,
        idempotency_key   char(64)          NOT NULL,
        iniciado_em       datetime2(0)      NOT NULL,
        finalizado_em     datetime2(0)      NOT NULL,
        exit_code         int               NOT NULL,
        estado_execucao   varchar(20)       NOT NULL
            CONSTRAINT CK_pentaho_log_execucao_estado
            CHECK (estado_execucao IN ('SUCESSO', 'FALHA')),
        log_caminho       nvarchar(2048)    NOT NULL,
        log_sha256        char(64)          NOT NULL,
        tamanho_bytes     bigint            NOT NULL
            CONSTRAINT CK_pentaho_log_execucao_tamanho CHECK (tamanho_bytes >= 0),
        host              nvarchar(200)     NULL,
        criado_em         datetime2(0)      NOT NULL
            CONSTRAINT DF_pentaho_log_execucao_criado DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_pentaho_log_execucao_idempotency UNIQUE (idempotency_key)
    );
END;
GO

IF OBJECT_ID('dbo.pentaho_log_fila', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.pentaho_log_fila
    (
        fila_id                 uniqueidentifier NOT NULL
            CONSTRAINT PK_pentaho_log_fila PRIMARY KEY
            CONSTRAINT DF_pentaho_log_fila_id DEFAULT NEWID(),
        execucao_id             uniqueidentifier NOT NULL,
        estado                  varchar(20)       NOT NULL
            CONSTRAINT CK_pentaho_log_fila_estado
            CHECK (estado IN
            (
                'AGUARDANDO', 'PROCESSANDO', 'FALHA', 'CONCLUIDO', 'DLQ',
                'EXPURGANDO', 'EXPURGO_FALHA', 'EXPURGO_DLQ', 'EXPURGADO'
            )),
        tentativas              tinyint           NOT NULL
            CONSTRAINT DF_pentaho_log_fila_tentativas DEFAULT 0,
        disponivel_em           datetime2(0)      NOT NULL
            CONSTRAINT DF_pentaho_log_fila_disponivel DEFAULT SYSUTCDATETIME(),
        bloqueio_ate            datetime2(0)      NULL,
        consumidor              nvarchar(200)     NULL,
        arquivo_destino         nvarchar(2048)    NULL,
        retencao_ate            datetime2(0)      NULL,
        ultimo_erro             nvarchar(1000)    NULL,
        expurgo_tentativas      tinyint           NOT NULL
            CONSTRAINT DF_pentaho_log_fila_expurgo_tentativas DEFAULT 0,
        expurgo_bloqueio_ate    datetime2(0)      NULL,
        expurgo_consumidor      nvarchar(200)     NULL,
        expurgo_ultimo_erro     nvarchar(1000)    NULL,
        expurgado_em            datetime2(0)      NULL,
        criado_em               datetime2(0)      NOT NULL
            CONSTRAINT DF_pentaho_log_fila_criado DEFAULT SYSUTCDATETIME(),
        atualizado_em           datetime2(0)      NOT NULL
            CONSTRAINT DF_pentaho_log_fila_atualizado DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_pentaho_log_fila_execucao
            FOREIGN KEY (execucao_id) REFERENCES dbo.pentaho_log_execucao(execucao_id),
        CONSTRAINT UQ_pentaho_log_fila_execucao UNIQUE (execucao_id)
    );
END;
GO

IF NOT EXISTS
(
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pentaho_log_fila')
      AND name = 'IX_pentaho_log_fila_reserva'
)
BEGIN
    CREATE INDEX IX_pentaho_log_fila_reserva
        ON dbo.pentaho_log_fila (estado, disponivel_em, bloqueio_ate, tentativas, criado_em)
        INCLUDE (execucao_id);
END;
GO

IF NOT EXISTS
(
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.pentaho_log_fila')
      AND name = 'IX_pentaho_log_fila_expurgo'
)
BEGIN
    CREATE INDEX IX_pentaho_log_fila_expurgo
        ON dbo.pentaho_log_fila (estado, retencao_ate, expurgo_bloqueio_ate, expurgo_tentativas)
        INCLUDE (execucao_id, arquivo_destino);
END;
GO

IF OBJECT_ID('dbo.pentaho_log_quarentena', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.pentaho_log_quarentena
    (
        lote_id        uniqueidentifier NOT NULL,
        indice_origem  int              NOT NULL,
        identificador  nvarchar(300)    NULL,
        motivo         varchar(60)      NOT NULL,
        registro_json  nvarchar(max)    NOT NULL,
        criado_em      datetime2(0)     NOT NULL
            CONSTRAINT DF_pentaho_log_quarentena_criado DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_pentaho_log_quarentena PRIMARY KEY (lote_id, indice_origem)
    );
END;
GO

CREATE OR ALTER PROCEDURE dbo.sp_pentaho_log_ingestir_json
    @lote_id uniqueidentifier,
    @payload nvarchar(max)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF ISJSON(@payload) <> 1
        THROW 51000, 'Payload JSON invalido.', 1;

    CREATE TABLE #Entrada
    (
        indice_origem   int              NOT NULL,
        execucao_id_txt nvarchar(50)     NULL,
        execucao_id     uniqueidentifier NULL,
        correlation_txt nvarchar(50)     NULL,
        correlation_id  uniqueidentifier NULL,
        processo        nvarchar(200)    NULL,
        execution_key   nvarchar(300)    NULL,
        idempotency_key nvarchar(64)     NULL,
        iniciado_em     datetime2(0)     NULL,
        finalizado_em   datetime2(0)     NULL,
        exit_code       int              NULL,
        estado_execucao varchar(20)      NULL,
        log_caminho     nvarchar(2048)   NULL,
        log_sha256      nvarchar(64)     NULL,
        tamanho_bytes   bigint           NULL,
        host            nvarchar(200)    NULL,
        registro_json   nvarchar(max)    NOT NULL,
        motivo          varchar(60)      NULL
    );

    INSERT INTO #Entrada
    (
        indice_origem, execucao_id_txt, execucao_id,
        correlation_txt, correlation_id, processo, execution_key,
        idempotency_key, iniciado_em, finalizado_em, exit_code,
        estado_execucao, log_caminho, log_sha256, tamanho_bytes,
        host, registro_json, motivo
    )
    SELECT
        CONVERT(int, j.[key]),
        x.execucao_id,
        TRY_CONVERT(uniqueidentifier, x.execucao_id),
        x.correlation_id,
        TRY_CONVERT(uniqueidentifier, x.correlation_id),
        x.processo,
        x.execution_key,
        LOWER(x.idempotency_key),
        x.iniciado_em,
        x.finalizado_em,
        x.exit_code,
        x.estado_execucao,
        x.log_caminho,
        LOWER(x.log_sha256),
        x.tamanho_bytes,
        x.host,
        j.[value],
        CASE
            WHEN TRY_CONVERT(uniqueidentifier, x.execucao_id) IS NULL THEN 'EXECUCAO_ID_INVALIDO'
            WHEN TRY_CONVERT(uniqueidentifier, x.correlation_id) IS NULL THEN 'CORRELATION_ID_INVALIDO'
            WHEN NULLIF(LTRIM(RTRIM(x.processo)), '') IS NULL THEN 'PROCESSO_INVALIDO'
            WHEN NULLIF(LTRIM(RTRIM(x.execution_key)), '') IS NULL THEN 'EXECUTION_KEY_INVALIDA'
            WHEN LEN(ISNULL(x.idempotency_key, '')) <> 64
                 OR x.idempotency_key LIKE '%[^0-9A-Fa-f]%' THEN 'IDEMPOTENCY_KEY_INVALIDA'
            WHEN x.iniciado_em IS NULL OR x.finalizado_em IS NULL THEN 'DATA_EXECUCAO_INVALIDA'
            WHEN x.finalizado_em < x.iniciado_em THEN 'INTERVALO_EXECUCAO_INVALIDO'
            WHEN x.exit_code IS NULL THEN 'EXIT_CODE_INVALIDO'
            WHEN x.estado_execucao NOT IN ('SUCESSO', 'FALHA') THEN 'ESTADO_EXECUCAO_INVALIDO'
            WHEN NULLIF(LTRIM(RTRIM(x.log_caminho)), '') IS NULL THEN 'LOG_CAMINHO_INVALIDO'
            WHEN LEN(ISNULL(x.log_sha256, '')) <> 64
                 OR x.log_sha256 LIKE '%[^0-9A-Fa-f]%' THEN 'LOG_SHA256_INVALIDO'
            WHEN x.tamanho_bytes IS NULL OR x.tamanho_bytes < 0 THEN 'TAMANHO_INVALIDO'
            ELSE NULL
        END
    FROM OPENJSON(@payload) AS j
    CROSS APPLY OPENJSON(j.[value])
    WITH
    (
        execucao_id       nvarchar(50)   '$.execucao_id',
        correlation_id    nvarchar(50)   '$.correlation_id',
        processo          nvarchar(200)  '$.processo',
        execution_key     nvarchar(300)  '$.execution_key',
        idempotency_key   nvarchar(64)   '$.idempotency_key',
        iniciado_em       datetime2(0)   '$.iniciado_em',
        finalizado_em     datetime2(0)   '$.finalizado_em',
        exit_code         int            '$.exit_code',
        estado_execucao   varchar(20)    '$.estado_execucao',
        log_caminho       nvarchar(2048) '$.log_caminho',
        log_sha256        nvarchar(64)   '$.log_sha256',
        tamanho_bytes     bigint         '$.tamanho_bytes',
        host              nvarchar(200)  '$.host'
    ) AS x;

    DECLARE @Inseridos int = 0;
    DECLARE @Quarentenados int = 0;

    BEGIN TRANSACTION;

    INSERT INTO dbo.pentaho_log_quarentena
    (
        lote_id, indice_origem, identificador, motivo, registro_json
    )
    SELECT
        @lote_id,
        e.indice_origem,
        COALESCE(e.execucao_id_txt, e.idempotency_key),
        e.motivo,
        e.registro_json
    FROM #Entrada AS e
    WHERE e.motivo IS NOT NULL
      AND NOT EXISTS
      (
          SELECT 1
          FROM dbo.pentaho_log_quarentena AS q WITH (UPDLOCK, HOLDLOCK)
          WHERE q.lote_id = @lote_id
            AND q.indice_origem = e.indice_origem
      );
    SET @Quarentenados += @@ROWCOUNT;

    INSERT INTO dbo.pentaho_log_quarentena
    (
        lote_id, indice_origem, identificador, motivo, registro_json
    )
    SELECT
        @lote_id,
        e.indice_origem,
        e.execucao_id_txt,
        'CONFLITO_IDEMPOTENCIA',
        e.registro_json
    FROM #Entrada AS e
    WHERE e.motivo IS NULL
      AND
      (
          EXISTS
          (
              SELECT 1
              FROM dbo.pentaho_log_execucao AS x WITH (UPDLOCK, HOLDLOCK)
              WHERE x.execucao_id = e.execucao_id
                AND x.idempotency_key <> e.idempotency_key
          )
          OR EXISTS
          (
              SELECT 1
              FROM dbo.pentaho_log_execucao AS x WITH (UPDLOCK, HOLDLOCK)
              WHERE x.idempotency_key = e.idempotency_key
                AND x.execucao_id <> e.execucao_id
          )
      )
      AND NOT EXISTS
      (
          SELECT 1
          FROM dbo.pentaho_log_quarentena AS q WITH (UPDLOCK, HOLDLOCK)
          WHERE q.lote_id = @lote_id
            AND q.indice_origem = e.indice_origem
      );
    SET @Quarentenados += @@ROWCOUNT;

    INSERT INTO dbo.pentaho_log_execucao
    (
        execucao_id, correlation_id, processo, execution_key,
        idempotency_key, iniciado_em, finalizado_em, exit_code,
        estado_execucao, log_caminho, log_sha256, tamanho_bytes, host
    )
    SELECT
        e.execucao_id,
        e.correlation_id,
        e.processo,
        e.execution_key,
        e.idempotency_key,
        e.iniciado_em,
        e.finalizado_em,
        e.exit_code,
        e.estado_execucao,
        e.log_caminho,
        e.log_sha256,
        e.tamanho_bytes,
        e.host
    FROM #Entrada AS e
    WHERE e.motivo IS NULL
      AND NOT EXISTS
      (
          SELECT 1
          FROM dbo.pentaho_log_quarentena AS q
          WHERE q.lote_id = @lote_id
            AND q.indice_origem = e.indice_origem
      )
      AND NOT EXISTS
      (
          SELECT 1
          FROM dbo.pentaho_log_execucao AS x WITH (UPDLOCK, HOLDLOCK)
          WHERE x.execucao_id = e.execucao_id
             OR x.idempotency_key = e.idempotency_key
      );
    SET @Inseridos = @@ROWCOUNT;

    INSERT INTO dbo.pentaho_log_fila
    (
        execucao_id, estado, tentativas, disponivel_em
    )
    SELECT
        x.execucao_id,
        'AGUARDANDO',
        0,
        SYSUTCDATETIME()
    FROM #Entrada AS e
    INNER JOIN dbo.pentaho_log_execucao AS x
        ON x.execucao_id = e.execucao_id
       AND x.idempotency_key = e.idempotency_key
    WHERE e.motivo IS NULL
      AND NOT EXISTS
      (
          SELECT 1
          FROM dbo.pentaho_log_quarentena AS q
          WHERE q.lote_id = @lote_id
            AND q.indice_origem = e.indice_origem
      )
      AND NOT EXISTS
      (
          SELECT 1
          FROM dbo.pentaho_log_fila AS f WITH (UPDLOCK, HOLDLOCK)
          WHERE f.execucao_id = x.execucao_id
      );

    COMMIT TRANSACTION;

    SELECT
        @Inseridos AS inseridos,
        @Quarentenados AS quarentenados;
END;
GO

CREATE OR ALTER PROCEDURE dbo.sp_pentaho_log_reservar
    @consumidor nvarchar(200),
    @quantidade int = 3,
    @lease_segundos int = 300,
    @agora datetime2(0) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @quantidade <= 0 OR @quantidade > 100
        THROW 51001, 'Quantidade de reserva invalida.', 1;
    IF @lease_segundos <= 0
        THROW 51002, 'Lease invalido.', 1;
    IF NULLIF(LTRIM(RTRIM(@consumidor)), '') IS NULL
        THROW 51003, 'Consumidor obrigatorio.', 1;

    SET @agora = COALESCE(@agora, SYSUTCDATETIME());

    DECLARE @Reservados TABLE
    (
        fila_id       uniqueidentifier NOT NULL,
        execucao_id   uniqueidentifier NOT NULL,
        tentativa     tinyint          NOT NULL,
        bloqueio_ate  datetime2(0)     NOT NULL
    );

    BEGIN TRANSACTION;

    ;WITH Candidatos AS
    (
        SELECT TOP (@quantidade)
            f.fila_id
        FROM dbo.pentaho_log_fila AS f WITH (UPDLOCK, READPAST, ROWLOCK)
        WHERE f.tentativas < 3
          AND
          (
              (
                  f.estado IN ('AGUARDANDO', 'FALHA')
                  AND f.disponivel_em <= @agora
              )
              OR
              (
                  f.estado = 'PROCESSANDO'
                  AND f.bloqueio_ate <= @agora
              )
          )
        ORDER BY
            CASE f.estado
                WHEN 'FALHA' THEN 1
                WHEN 'AGUARDANDO' THEN 2
                ELSE 3
            END,
            f.disponivel_em,
            f.criado_em,
            f.fila_id
    )
    UPDATE f
       SET estado = 'PROCESSANDO',
           tentativas = tentativas + 1,
           bloqueio_ate = DATEADD(SECOND, @lease_segundos, @agora),
           consumidor = @consumidor,
           ultimo_erro = NULL,
           atualizado_em = @agora
    OUTPUT
        inserted.fila_id,
        inserted.execucao_id,
        inserted.tentativas,
        inserted.bloqueio_ate
    INTO @Reservados
    FROM dbo.pentaho_log_fila AS f
    INNER JOIN Candidatos AS c
        ON c.fila_id = f.fila_id;

    COMMIT TRANSACTION;

    SELECT
        r.fila_id,
        r.execucao_id,
        e.correlation_id,
        e.processo,
        e.iniciado_em,
        e.log_caminho,
        e.log_sha256,
        e.tamanho_bytes,
        r.tentativa,
        r.bloqueio_ate
    FROM @Reservados AS r
    INNER JOIN dbo.pentaho_log_execucao AS e
        ON e.execucao_id = r.execucao_id
    ORDER BY e.iniciado_em, r.fila_id;
END;
GO

CREATE OR ALTER PROCEDURE dbo.sp_pentaho_log_concluir
    @fila_id uniqueidentifier,
    @consumidor nvarchar(200),
    @arquivo_destino nvarchar(2048),
    @retencao_dias int = 30,
    @agora datetime2(0) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @retencao_dias <= 0
        THROW 51004, 'Retencao invalida.', 1;
    SET @agora = COALESCE(@agora, SYSUTCDATETIME());

    UPDATE dbo.pentaho_log_fila
       SET estado = 'CONCLUIDO',
           arquivo_destino = @arquivo_destino,
           retencao_ate = DATEADD(DAY, @retencao_dias, @agora),
           bloqueio_ate = NULL,
           consumidor = NULL,
           ultimo_erro = NULL,
           atualizado_em = @agora
     WHERE fila_id = @fila_id
       AND estado = 'PROCESSANDO'
       AND consumidor = @consumidor;

    IF @@ROWCOUNT <> 1
        THROW 51005, 'Reserva nao pertence ao consumidor ou nao esta PROCESSANDO.', 1;
END;
GO

CREATE OR ALTER PROCEDURE dbo.sp_pentaho_log_falhar
    @fila_id uniqueidentifier,
    @consumidor nvarchar(200),
    @erro nvarchar(1000),
    @retry_segundos int = 120,
    @agora datetime2(0) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @retry_segundos <= 0
        THROW 51006, 'Retry invalido.', 1;
    SET @agora = COALESCE(@agora, SYSUTCDATETIME());

    DECLARE @Resultado TABLE (estado varchar(20), tentativas tinyint);

    UPDATE dbo.pentaho_log_fila
       SET estado = CASE WHEN tentativas >= 3 THEN 'DLQ' ELSE 'FALHA' END,
           disponivel_em = CASE
               WHEN tentativas >= 3 THEN disponivel_em
               ELSE DATEADD(SECOND, @retry_segundos, @agora)
           END,
           bloqueio_ate = NULL,
           consumidor = NULL,
           ultimo_erro = LEFT(@erro, 1000),
           atualizado_em = @agora
    OUTPUT inserted.estado, inserted.tentativas INTO @Resultado
     WHERE fila_id = @fila_id
       AND estado = 'PROCESSANDO'
       AND consumidor = @consumidor;

    IF NOT EXISTS (SELECT 1 FROM @Resultado)
        THROW 51007, 'Falha nao pode ser registrada sem reserva valida.', 1;

    SELECT estado, tentativas FROM @Resultado;
END;
GO

CREATE OR ALTER PROCEDURE dbo.sp_pentaho_log_reservar_expurgo
    @consumidor nvarchar(200),
    @quantidade int = 3,
    @lease_segundos int = 300,
    @agora datetime2(0) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @quantidade <= 0 OR @quantidade > 100
        THROW 51008, 'Quantidade de expurgo invalida.', 1;
    IF @lease_segundos <= 0
        THROW 51009, 'Lease de expurgo invalido.', 1;
    SET @agora = COALESCE(@agora, SYSUTCDATETIME());

    DECLARE @Reservados TABLE
    (
        fila_id uniqueidentifier NOT NULL,
        execucao_id uniqueidentifier NOT NULL,
        tentativa tinyint NOT NULL,
        arquivo_destino nvarchar(2048) NOT NULL
    );

    BEGIN TRANSACTION;

    ;WITH Candidatos AS
    (
        SELECT TOP (@quantidade) f.fila_id
        FROM dbo.pentaho_log_fila AS f WITH (UPDLOCK, READPAST, ROWLOCK)
        WHERE f.expurgo_tentativas < 3
          AND f.arquivo_destino IS NOT NULL
          AND
          (
              (
                  f.estado IN ('CONCLUIDO', 'EXPURGO_FALHA')
                  AND f.retencao_ate <= @agora
              )
              OR
              (
                  f.estado = 'EXPURGANDO'
                  AND f.expurgo_bloqueio_ate <= @agora
              )
          )
        ORDER BY f.retencao_ate, f.criado_em, f.fila_id
    )
    UPDATE f
       SET estado = 'EXPURGANDO',
           expurgo_tentativas = expurgo_tentativas + 1,
           expurgo_bloqueio_ate = DATEADD(SECOND, @lease_segundos, @agora),
           expurgo_consumidor = @consumidor,
           expurgo_ultimo_erro = NULL,
           atualizado_em = @agora
    OUTPUT
        inserted.fila_id,
        inserted.execucao_id,
        inserted.expurgo_tentativas,
        inserted.arquivo_destino
    INTO @Reservados
    FROM dbo.pentaho_log_fila AS f
    INNER JOIN Candidatos AS c
        ON c.fila_id = f.fila_id;

    COMMIT TRANSACTION;

    SELECT
        r.fila_id,
        r.execucao_id,
        e.correlation_id,
        e.log_sha256,
        r.arquivo_destino,
        r.tentativa
    FROM @Reservados AS r
    INNER JOIN dbo.pentaho_log_execucao AS e
        ON e.execucao_id = r.execucao_id
    ORDER BY r.fila_id;
END;
GO

CREATE OR ALTER PROCEDURE dbo.sp_pentaho_log_concluir_expurgo
    @fila_id uniqueidentifier,
    @consumidor nvarchar(200),
    @agora datetime2(0) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    SET @agora = COALESCE(@agora, SYSUTCDATETIME());

    UPDATE dbo.pentaho_log_fila
       SET estado = 'EXPURGADO',
           expurgado_em = @agora,
           expurgo_bloqueio_ate = NULL,
           expurgo_consumidor = NULL,
           expurgo_ultimo_erro = NULL,
           atualizado_em = @agora
     WHERE fila_id = @fila_id
       AND estado = 'EXPURGANDO'
       AND expurgo_consumidor = @consumidor;

    IF @@ROWCOUNT <> 1
        THROW 51010, 'Reserva de expurgo invalida.', 1;
END;
GO

CREATE OR ALTER PROCEDURE dbo.sp_pentaho_log_falhar_expurgo
    @fila_id uniqueidentifier,
    @consumidor nvarchar(200),
    @erro nvarchar(1000),
    @retry_segundos int = 120,
    @agora datetime2(0) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @retry_segundos <= 0
        THROW 51011, 'Retry de expurgo invalido.', 1;
    SET @agora = COALESCE(@agora, SYSUTCDATETIME());

    UPDATE dbo.pentaho_log_fila
       SET estado = CASE
               WHEN expurgo_tentativas >= 3 THEN 'EXPURGO_DLQ'
               ELSE 'EXPURGO_FALHA'
           END,
           retencao_ate = CASE
               WHEN expurgo_tentativas >= 3 THEN retencao_ate
               ELSE DATEADD(SECOND, @retry_segundos, @agora)
           END,
           expurgo_bloqueio_ate = NULL,
           expurgo_consumidor = NULL,
           expurgo_ultimo_erro = LEFT(@erro, 1000),
           atualizado_em = @agora
     WHERE fila_id = @fila_id
       AND estado = 'EXPURGANDO'
       AND expurgo_consumidor = @consumidor;

    IF @@ROWCOUNT <> 1
        THROW 51012, 'Falha de expurgo sem reserva valida.', 1;
END;
GO
