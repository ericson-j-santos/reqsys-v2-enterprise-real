-- #2861 · Migração rotina de e-mail Prospecção Movimento — Portabilidade Consignado
-- Rollback da versão V1 — remove as 4 views se existirem (idempotente: rodar
-- em um banco onde elas já não existem não gera erro).
--
-- Executado só sob confirmação explícita (scripts/aplicar_movimento_email_views.py
-- rollback --confirmar) — nunca automaticamente.

DROP VIEW IF EXISTS dbo.vw_prospeccao_movimento_fechamento_diario;
DROP VIEW IF EXISTS dbo.vw_prospeccao_movimento_pendencias_cadastro;
DROP VIEW IF EXISTS dbo.vw_prospeccao_movimento_pendencias_historicas;
DROP VIEW IF EXISTS dbo.vw_prospeccao_movimento_pendencias_observacao;
