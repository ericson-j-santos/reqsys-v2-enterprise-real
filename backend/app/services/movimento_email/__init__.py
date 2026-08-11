"""Pipeline Python da rotina de e-mail diário de Prospecção Movimento —
Portabilidade Consignado (Funcionalidade #2861 — Migrar rotina de e-mail
para Python).

Substitui o modelo antigo (SSRS + agendamento nativo) por um pipeline
ETL + renderização HTML + fila de envio, mantendo o domínio livre de
SQL Server, SMTP ou framework (ADR-001):

    extração (repository) -> transformação (transform) -> renderização
    (email_service) -> fila (queue_repository) -> consumer -> SMTP

Ver docs/architecture/movimento-email-pipeline.md para o estado atual,
o estado alvo e os gaps pendentes (ADR-012).
"""
