-- Fonte autogerida da Prospecção Movimento para ambiente privado do ReqSys.
-- Não contém seed sintético e não cria login/senha.
IF SCHEMA_ID('owner_movimento') IS NULL EXEC('CREATE SCHEMA owner_movimento');

IF OBJECT_ID('owner_movimento.fechamento_diario','U') IS NULL
CREATE TABLE owner_movimento.fechamento_diario(
  indicador varchar(200) NOT NULL,
  valor varchar(100) NOT NULL,
  observacao varchar(500) NULL,
  data_referencia date NOT NULL,
  source_record_hash char(64) NOT NULL,
  ingested_at datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME()
);

IF OBJECT_ID('owner_movimento.pendencias_cadastro','U') IS NULL
CREATE TABLE owner_movimento.pendencias_cadastro(
  protocolo varchar(50) NOT NULL,
  cliente varchar(200) NOT NULL,
  cpf varchar(11) NOT NULL,
  pendencia varchar(200) NOT NULL,
  dias_em_aberto int NOT NULL,
  responsavel varchar(120) NULL,
  data_referencia date NOT NULL,
  source_record_hash char(64) NOT NULL,
  ingested_at datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME()
);

IF OBJECT_ID('owner_movimento.pendencias_historicas','U') IS NULL
CREATE TABLE owner_movimento.pendencias_historicas(
  periodo_referencia varchar(20) NOT NULL,
  pendencia varchar(200) NOT NULL,
  quantidade int NOT NULL,
  percentual decimal(5,2) NOT NULL,
  data_referencia date NOT NULL,
  source_record_hash char(64) NOT NULL,
  ingested_at datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME()
);

IF OBJECT_ID('owner_movimento.pendencias_observacao','U') IS NULL
CREATE TABLE owner_movimento.pendencias_observacao(
  protocolo varchar(50) NOT NULL,
  tipo_inconsistencia varchar(120) NOT NULL,
  descricao varchar(500) NOT NULL,
  etapa varchar(120) NULL,
  data_referencia date NOT NULL,
  source_record_hash char(64) NOT NULL,
  ingested_at datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME()
);

IF OBJECT_ID('owner_movimento.ingest_runs','U') IS NULL
CREATE TABLE owner_movimento.ingest_runs(
  id bigint IDENTITY(1,1) PRIMARY KEY,
  correlation_id varchar(80) NOT NULL,
  data_referencia date NOT NULL,
  payload_hash char(64) NOT NULL,
  row_counts_json nvarchar(max) NOT NULL,
  status varchar(30) NOT NULL,
  created_at datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME()
);

EXEC('CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_fechamento_diario AS
SELECT indicador,valor,observacao,data_referencia FROM owner_movimento.fechamento_diario');
EXEC('CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_cadastro AS
SELECT protocolo,cliente,cpf,pendencia,dias_em_aberto,responsavel,data_referencia FROM owner_movimento.pendencias_cadastro');
EXEC('CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_historicas AS
SELECT periodo_referencia,pendencia,quantidade,percentual,data_referencia FROM owner_movimento.pendencias_historicas');
EXEC('CREATE OR ALTER VIEW dbo.vw_prospeccao_movimento_pendencias_observacao AS
SELECT protocolo,tipo_inconsistencia,descricao,etapa,data_referencia FROM owner_movimento.pendencias_observacao');
