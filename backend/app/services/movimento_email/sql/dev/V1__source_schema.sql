-- Infraestrutura DEV autocontida para Prospecção Movimento.
-- Cria somente schema/tabelas-fonte dentro do banco já selecionado.
-- Não cria usuários, logins, segredos nem permissões administrativas.

IF SCHEMA_ID('movimento_src') IS NULL
    EXEC('CREATE SCHEMA movimento_src');

IF OBJECT_ID('movimento_src.fechamento_diario', 'U') IS NULL
BEGIN
    CREATE TABLE movimento_src.fechamento_diario (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        indicador VARCHAR(200) NOT NULL,
        valor VARCHAR(100) NOT NULL,
        observacao VARCHAR(500) NULL,
        data_referencia DATE NOT NULL,
        source_tag VARCHAR(120) NOT NULL,
        loaded_at DATETIME2(0) NOT NULL
            CONSTRAINT DF_movimento_src_fechamento_loaded_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID('movimento_src.pendencias_cadastro', 'U') IS NULL
BEGIN
    CREATE TABLE movimento_src.pendencias_cadastro (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        protocolo VARCHAR(50) NOT NULL,
        cliente VARCHAR(200) NOT NULL,
        cpf VARCHAR(11) NOT NULL,
        pendencia VARCHAR(200) NOT NULL,
        dias_em_aberto INT NOT NULL,
        responsavel VARCHAR(120) NULL,
        data_referencia DATE NOT NULL,
        source_tag VARCHAR(120) NOT NULL,
        loaded_at DATETIME2(0) NOT NULL
            CONSTRAINT DF_movimento_src_cadastro_loaded_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID('movimento_src.pendencias_historicas', 'U') IS NULL
BEGIN
    CREATE TABLE movimento_src.pendencias_historicas (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        periodo_referencia VARCHAR(20) NOT NULL,
        pendencia VARCHAR(200) NOT NULL,
        quantidade INT NOT NULL,
        percentual DECIMAL(5,2) NOT NULL,
        data_referencia DATE NOT NULL,
        source_tag VARCHAR(120) NOT NULL,
        loaded_at DATETIME2(0) NOT NULL
            CONSTRAINT DF_movimento_src_historicas_loaded_at DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID('movimento_src.pendencias_observacao', 'U') IS NULL
BEGIN
    CREATE TABLE movimento_src.pendencias_observacao (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        protocolo VARCHAR(50) NOT NULL,
        tipo_inconsistencia VARCHAR(120) NOT NULL,
        descricao VARCHAR(500) NOT NULL,
        etapa VARCHAR(120) NULL,
        data_referencia DATE NOT NULL,
        source_tag VARCHAR(120) NOT NULL,
        loaded_at DATETIME2(0) NOT NULL
            CONSTRAINT DF_movimento_src_observacao_loaded_at DEFAULT SYSUTCDATETIME()
    );
END;
