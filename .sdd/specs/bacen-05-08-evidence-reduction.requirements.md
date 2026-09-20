# BACEN-05/08 — redução de ambiguidade de evidência

## Objetivo

Fortalecer a verificabilidade das evidências já existentes dos controles BACEN-05 e BACEN-08 sem tocar produção, criar evidência institucional, preencher dados humanos ausentes ou promover controles de `partial` para `implemented`.

## Requisitos

1. BACEN-05 deve validar referências locais de evidência usadas no inventário PROD.
2. Referência local inexistente, absoluta ou fora do repositório deve falhar fechada.
3. Fornecedores sem prova suficiente permanecem `UNVERIFIED`; ausência de evidência nunca implica `NOT_USED_IN_PROD`.
4. BACEN-08 deve materializar no artifact a referência autenticada de autodesignação já registrada, incluindo URL, SHA-256, ator e data.
5. A evidência autenticada de autodesignação deve permanecer semanticamente separada da designação formal.
6. BACEN-08 deve continuar `partial` enquanto designação formal e sign-off anual estiverem pendentes.
7. `production_touched` deve permanecer `false` e promoção automática de status deve permanecer proibida.
8. Para T01, T06 e T14, referências documentais oficiais podem ser registradas apenas como evidência documental; descoberta de DPA/termos não equivale a aceite jurídico.
9. Fly.io só pode ter DPA marcado como ativo quando existir referência verificável da assinatura do cliente.
10. O pacote de formalização BACEN-08 deve preparar a captura futura, mas não pode inferir assinatura, designação formal ou sign-off do relatório a partir de texto genérico ou ação automatizada.

## Critérios de aceite

- [ ] O inventário atual BACEN-05 valida 14 fornecedores, com 3 `USED_IN_PROD`, 0 `NOT_USED_IN_PROD` e 11 `UNVERIFIED`.
- [ ] T01, T06 e T14 possuem referências locais existentes e são expostos como classificações com evidência local validada.
- [ ] Referência inexistente falha com erro explícito.
- [ ] Path absoluto ou que escape do repositório falha fechado.
- [ ] Registro documental contém somente T01, T06 e T14, com fontes oficiais HTTPS nos domínios esperados.
- [ ] Microsoft DPA, GitHub DPA e Fly.io DPA/compliance ficam registrados sem afirmar aceite jurídico.
- [ ] Fly.io permanece `pending_customer_signature` sem referência de assinatura do cliente.
- [ ] BACEN-08 expõe `authenticated_designation_evidence_structurally_valid=true` para a referência autenticada existente.
- [ ] Hash inválido da evidência autenticada faz a prontidão técnica falhar fechada.
- [ ] `formal_designation_present=false` permanece enquanto o bloco formal não estiver preenchido.
- [ ] Pacote BACEN-08 mantém designação formal e relatório anual em estados pendentes de ato humano explícito.
- [ ] `remaining_formal_blockers` identifica designação executiva formal e sign-off formal do relatório anual.
- [ ] `control_status=partial`, `automatic_status_promotion_allowed=false` e `production_touched=false`.
- [ ] O cenário de estágio PROD sem governança formal continua bloqueando.
- [ ] Nenhum deploy PROD, bypass Fly, alteração de segredo ou fabricação de evidência é executado.

## Evidência de teste

- `tests/test_validate_bacen_prod_third_party_scope.py`
- `tests/test_bacen_deferred_executive_governance.py`
- `tests/test_validate_bacen_05_08_canonical_evidence.py`

## Rastreabilidade

Issue #1615, PR #1839 e incremento documental de 2026-09-20.
