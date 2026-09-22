# CMN-4893 — exceção técnica temporária para PROD até 2026-12-31

## Objetivo

Permitir que a prontidão técnica para PROD seja avaliada enquanto
`institutional_scope.legal_entity` e `institutional_scope.entity_type` permanecem
indisponíveis em fonte institucional autoritativa, sem fabricar evidência,
sem transformar `pending_decision` em decisão regulatória final e sem ignorar
qualquer outro gate produtivo.

## Autorização

- Issue: #1505.
- Aprovação explícita: `https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1505#issuecomment-5782326463`.
- Decisão humana de intenção: `applicable`.
- Validade máxima: `2026-12-31`.

## Requisitos

1. A exceção deve cobrir exclusivamente o blocker `family_applicability_pending`.
2. Os únicos campos temporariamente diferidos são
   `institutional_scope.legal_entity` e `institutional_scope.entity_type`.
3. O registro autoritativo deve permanecer `pending_decision`.
4. A avaliação técnica pode usar `applicable` apenas como decisão efetiva interna
   durante PROD e somente enquanto a exceção estiver ativa.
5. `regulatory_finality_allowed=false` e
   `regulatory_compliance_claim_allowed=false`.
6. Valores fictícios e inferência automática permanecem proibidos.
7. RSFN, Pix, STR e SMF permanecem independentes e `unknown` sem evidência própria.
8. Todos os demais blockers BACEN, evidências vencidas, gaps, approvals,
   branch protection, E2E e controles de produção permanecem bloqueadores.
9. A exceção é válida de 2026-09-22 a 2026-12-31, inclusive.
10. Em 2027-01-01 a exceção deve falhar fechada automaticamente.
11. Se a decisão autoritativa tornar-se final antes do prazo, a exceção deixa de ser aplicada.
12. A política NONPROD existente deve permanecer inalterada.

## Critérios de aceite

- [ ] Arquivo de exceção versionado e restrito a `prod`.
- [ ] Aprovação da issue #1505 referenciada.
- [ ] Validador rejeita escopos/campos/blockers adicionais.
- [ ] Exceção ativa em 2026-12-31.
- [ ] Exceção expirada em 2027-01-01.
- [ ] Decisão autoritativa continua `pending_decision` no relatório.
- [ ] Decisão efetiva técnica `applicable` só aparece durante PROD e com exceção ativa.
- [ ] Decisão real final desativa automaticamente o uso da exceção.
- [ ] Gate 2 e BACEN Production Hard Gate consomem a exceção.
- [ ] `legacy_allowed and gate2_allowed` continua obrigatório.
- [ ] Nenhum deploy PROD é executado por este incremento.
- [ ] Testes focados e Pre-PR Readiness Gate aprovados no HEAD exato.

## Evidência

- `tests/test_cmn4893_prod_technical_exception.py`
- `tests/test_bacen_production_readiness_wiring.py`
- `tests/test_bacen_production_hard_gate_contract.py`
