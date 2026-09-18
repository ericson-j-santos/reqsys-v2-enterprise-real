-- Fonte legado simulada para DEV/HML local. Não contém credenciais.
IF SCHEMA_ID('legacy_ssrs') IS NULL EXEC('CREATE SCHEMA legacy_ssrs');

IF OBJECT_ID('legacy_ssrs.fechamento_diario','U') IS NULL
CREATE TABLE legacy_ssrs.fechamento_diario(
 id BIGINT IDENTITY PRIMARY KEY,
 indicador VARCHAR(200) NOT NULL,
 valor VARCHAR(100) NOT NULL,
 observacao VARCHAR(500) NULL,
 data_referencia DATE NOT NULL,
 source_tag VARCHAR(120) NOT NULL
);

IF OBJECT_ID('legacy_ssrs.pendencias_cadastro','U') IS NULL
CREATE TABLE legacy_ssrs.pendencias_cadastro(
 id BIGINT IDENTITY PRIMARY KEY,
 protocolo VARCHAR(50) NOT NULL,
 cliente VARCHAR(200) NOT NULL,
 cpf VARCHAR(11) NOT NULL,
 pendencia VARCHAR(200) NOT NULL,
 dias_em_aberto INT NOT NULL,
 responsavel VARCHAR(120) NULL,
 data_referencia DATE NOT NULL,
 source_tag VARCHAR(120) NOT NULL
);

IF OBJECT_ID('legacy_ssrs.pendencias_historicas','U') IS NULL
CREATE TABLE legacy_ssrs.pendencias_historicas(
 id BIGINT IDENTITY PRIMARY KEY,
 periodo_referencia VARCHAR(20) NOT NULL,
 pendencia VARCHAR(200) NOT NULL,
 quantidade INT NOT NULL,
 percentual DECIMAL(5,2) NOT NULL,
 data_referencia DATE NOT NULL,
 source_tag VARCHAR(120) NOT NULL
);

IF OBJECT_ID('legacy_ssrs.pendencias_observacao','U') IS NULL
CREATE TABLE legacy_ssrs.pendencias_observacao(
 id BIGINT IDENTITY PRIMARY KEY,
 protocolo VARCHAR(50) NOT NULL,
 tipo_inconsistencia VARCHAR(120) NOT NULL,
 descricao VARCHAR(500) NOT NULL,
 etapa VARCHAR(120) NULL,
 data_referencia DATE NOT NULL,
 source_tag VARCHAR(120) NOT NULL
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_legacy_fd_tag_data' AND object_id=OBJECT_ID('legacy_ssrs.fechamento_diario'))
CREATE INDEX IX_legacy_fd_tag_data ON legacy_ssrs.fechamento_diario(source_tag,data_referencia);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_legacy_pc_tag_data' AND object_id=OBJECT_ID('legacy_ssrs.pendencias_cadastro'))
CREATE INDEX IX_legacy_pc_tag_data ON legacy_ssrs.pendencias_cadastro(source_tag,data_referencia);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_legacy_ph_tag_data' AND object_id=OBJECT_ID('legacy_ssrs.pendencias_historicas'))
CREATE INDEX IX_legacy_ph_tag_data ON legacy_ssrs.pendencias_historicas(source_tag,data_referencia);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_legacy_po_tag_data' AND object_id=OBJECT_ID('legacy_ssrs.pendencias_observacao'))
CREATE INDEX IX_legacy_po_tag_data ON legacy_ssrs.pendencias_observacao(source_tag,data_referencia);
