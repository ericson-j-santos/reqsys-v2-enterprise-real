# CMN-4893 — exceção temporária de dados institucionais

## Objetivo

Restaurar no `main` atual a exceção NONPROD já aprovada na issue #1505 para a ausência temporária de `institutional_scope.legal_entity` e `institutional_scope.entity_type`, sem fabricar evidência regulatória e sem liberar produção.

## Requisitos

1. A exceção deve valer somente para `pull_request`, `dev` e `stg`.
2. `prod` deve permanecer explicitamente bloqueado.
3. `production_allowed` e `regulatory_finality_allowed` devem permanecer `false`.
4. Valores fictícios e inferência automática de `legal_entity`/`entity_type` devem permanecer proibidos.
5. O arquivo autoritativo de decisão deve continuar em `pending_decision` enquanto os dois identificadores institucionais reais não existirem.
6. RSFN, Pix, STR e SMF devem permanecer independentes e sem inferência.
7. A exceção deve expirar em 2026-10-12 e qualquer renovação exige aprovação humana explícita.
8. A exceção não substitui evidência regulatória e não pode tocar produção.

## Critérios de aceite

- [ ] Arquivo da exceção existe na linha atual do PR.
- [ ] Escopos permitidos são exatamente `pull_request`, `dev` e `stg`.
- [ ] `prod` permanece bloqueado.
- [ ] `production_allowed=false`.
- [ ] `regulatory_finality_allowed=false`.
- [ ] `fabricated_values_allowed=false`.
- [ ] `automatic_inference_allowed=false`.
- [ ] Decisão autoritativa permanece `pending_decision`.
- [ ] Campos diferidos são exatamente `institutional_scope.legal_entity` e `institutional_scope.entity_type`.
- [ ] Expiração em 2026-10-12 e renovação humana explícita permanecem registradas.
- [ ] Teste automatizado confirma fail-closed e limites NONPROD.
- [ ] Nenhum deploy, segredo, permissão ou operação PROD é executado.

## Evidência de teste

- `tests/test_cmn4893_scope_data_exception.py`

## Rastreabilidade

- Issue #1505.
- Aprovação formal: `REQSYS-BACEN-CMN4893-APPROVAL-2026-09-18`.
- Exceção: `REQSYS-BACEN-CMN4893-SCOPE-DATA-EXCEPTION-2026-09-18`.
