DECLARE @tag VARCHAR(120)='REQSYS_SOURCE_E2E';
DECLARE @data DATE='2099-12-29';

DELETE FROM legacy_ssrs.fechamento_diario WHERE source_tag=@tag;
DELETE FROM legacy_ssrs.pendencias_cadastro WHERE source_tag=@tag;
DELETE FROM legacy_ssrs.pendencias_historicas WHERE source_tag=@tag;
DELETE FROM legacy_ssrs.pendencias_observacao WHERE source_tag=@tag;

INSERT INTO legacy_ssrs.fechamento_diario(indicador,valor,observacao,data_referencia,source_tag) VALUES
('SRC_QTD','21','origem dev separada',@data,@tag),
('SRC_VALOR','987.65','segunda linha da origem',@data,@tag);

INSERT INTO legacy_ssrs.pendencias_cadastro(protocolo,cliente,cpf,pendencia,dias_em_aberto,responsavel,data_referencia,source_tag)
VALUES('SRC-001','CLIENTE FONTE DEMO','00000000000','CADASTRO',4,'REQSYS-SOURCE-E2E',@data,@tag);

INSERT INTO legacy_ssrs.pendencias_historicas(periodo_referencia,pendencia,quantidade,percentual,data_referencia,source_tag)
VALUES('2099-12','CADASTRO',1,100.00,@data,@tag);

INSERT INTO legacy_ssrs.pendencias_observacao(protocolo,tipo_inconsistencia,descricao,etapa,data_referencia,source_tag)
VALUES('SRC-001','ORIGEM','registro sintético da fonte','CAPTURA',@data,@tag);
