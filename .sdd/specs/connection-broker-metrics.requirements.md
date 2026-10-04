# Métricas do Connection Broker

## Objetivo

Recuperar o incremento funcional do PR #69 sobre a arquitetura .NET atual, eliminando a divergência histórica sem reintroduzir alterações obsoletas de segurança ou de changelog.

## Requisitos

1. Expor `GET /api/connectors/metrics` e o alias `GET /v1/connectors/metrics`.
2. Responder em formato Prometheus `text/plain; version=0.0.4`.
3. Exportar total de capabilities, totais por status, totais por criticidade, total que exige confirmação humana e total de eventos de auditoria do Connection Broker.
4. Não exportar capability, usuário, `correlation_id`, detalhes de auditoria, credencial, token, segredo ou payload.
5. Sanitizar barras, aspas e quebras de linha em labels.
6. Manter cardinalidade limitada a status e criticidade.
7. Os dois aliases devem produzir as mesmas famílias de métricas.
8. Preservar o baseline Azure AD e os helpers de segurança atuais da `main`; a alteração histórica em `backend/tests/security_gate_helpers.py` não faz parte da recuperação.
9. Não adicionar deploy ou mutação de ambiente.

## Critérios de aceite

- Contrato preventivo Python verde no HEAD atual.
- Testes xUnit do endpoint verdes no CI .NET aplicável.
- SDD, segurança e governança verdes.
- Branch com `behind_by=0`, sem conflitos e mergeável.
