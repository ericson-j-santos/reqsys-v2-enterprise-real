/*
  Gestão de TI canônica — incremento P0.1
  Alvo: SQL Server 2017+
  Estratégia: somente adição; não altera a tabela requisitos.
*/
SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF OBJECT_ID(N'dbo.gestao_ti_servicos', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.gestao_ti_servicos (
        servico_id varchar(36) NOT NULL,
        codigo varchar(80) NOT NULL,
        nome nvarchar(200) NOT NULL,
        descricao nvarchar(1000) NULL,
        criticidade varchar(20) NOT NULL CONSTRAINT df_gti_servico_criticidade DEFAULT ('media'),
        responsavel_tecnico nvarchar(200) NOT NULL,
        responsavel_negocio nvarchar(200) NOT NULL,
        versao_catalogo int NOT NULL CONSTRAINT df_gti_servico_versao DEFAULT (1),
        ativo bit NOT NULL CONSTRAINT df_gti_servico_ativo DEFAULT (1),
        criado_em datetimeoffset NOT NULL CONSTRAINT df_gti_servico_criado DEFAULT (SYSDATETIMEOFFSET()),
        atualizado_em datetimeoffset NOT NULL CONSTRAINT df_gti_servico_atualizado DEFAULT (SYSDATETIMEOFFSET()),
        CONSTRAINT pk_gti_servicos PRIMARY KEY (servico_id),
        CONSTRAINT uq_gti_servicos_codigo UNIQUE (codigo),
        CONSTRAINT ck_gti_servicos_id CHECK (LEN(servico_id) = 36),
        CONSTRAINT ck_gti_servicos_criticidade CHECK (criticidade IN ('baixa','media','alta','critica')),
        CONSTRAINT ck_gti_servicos_versao CHECK (versao_catalogo > 0)
    );
END;

IF OBJECT_ID(N'dbo.gestao_ti_requisito_servico', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.gestao_ti_requisito_servico (
        vinculo_id int IDENTITY(1,1) NOT NULL,
        requisito_id int NOT NULL,
        servico_id varchar(36) NOT NULL,
        criado_por nvarchar(200) NOT NULL,
        correlation_id varchar(120) NOT NULL,
        criado_em datetimeoffset NOT NULL CONSTRAINT df_gti_vinculo_criado DEFAULT (SYSDATETIMEOFFSET()),
        CONSTRAINT pk_gti_requisito_servico PRIMARY KEY (vinculo_id),
        CONSTRAINT uq_gti_requisito_servico_requisito UNIQUE (requisito_id),
        CONSTRAINT fk_gti_vinculo_requisito FOREIGN KEY (requisito_id) REFERENCES dbo.requisitos(id),
        CONSTRAINT fk_gti_vinculo_servico FOREIGN KEY (servico_id) REFERENCES dbo.gestao_ti_servicos(servico_id)
    );
    CREATE INDEX ix_gti_vinculo_servico ON dbo.gestao_ti_requisito_servico(servico_id);
    CREATE INDEX ix_gti_vinculo_correlacao ON dbo.gestao_ti_requisito_servico(correlation_id);
END;

MERGE dbo.gestao_ti_servicos WITH (HOLDLOCK) AS destino
USING (VALUES (
    'bde5fd56-5b4f-4ee4-8d64-5aa5f755e3ef',
    'REQSYS',
    N'ReqSys',
    N'Plataforma corporativa de requisitos e gestão orientada a dados.',
    'alta',
    N'Equipe ReqSys',
    N'Gestão de Produtos',
    1,
    1
)) AS origem (
    servico_id, codigo, nome, descricao, criticidade,
    responsavel_tecnico, responsavel_negocio, versao_catalogo, ativo
)
ON destino.codigo = origem.codigo
WHEN MATCHED THEN UPDATE SET
    nome = origem.nome,
    descricao = origem.descricao,
    criticidade = origem.criticidade,
    responsavel_tecnico = origem.responsavel_tecnico,
    responsavel_negocio = origem.responsavel_negocio,
    ativo = origem.ativo,
    atualizado_em = SYSDATETIMEOFFSET()
WHEN NOT MATCHED THEN INSERT (
    servico_id, codigo, nome, descricao, criticidade,
    responsavel_tecnico, responsavel_negocio, versao_catalogo, ativo
) VALUES (
    origem.servico_id, origem.codigo, origem.nome, origem.descricao,
    origem.criticidade, origem.responsavel_tecnico,
    origem.responsavel_negocio, origem.versao_catalogo, origem.ativo
);

COMMIT TRANSACTION;

/*
  Reversão controlada, somente após validar ausência de consumidores:
  DROP TABLE dbo.gestao_ti_requisito_servico;
  DROP TABLE dbo.gestao_ti_servicos;
*/
