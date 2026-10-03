# SDD Readiness Gate — Requisitos

## Requisito 1 — especificação obrigatória
Toda mudança funcional deve alterar ou introduzir uma especificação em `.sdd/specs`.

## Requisito 2 — rastreabilidade
A especificação deve declarar `feature_name`, aprovação de requisitos e testes automatizados existentes.

## Critérios de aceite (Acceptance Criteria)
1. Mudança funcional sem especificação deve falhar com `SDD_SPEC_REQUIRED`.
2. Especificação sem critérios de aceite ou sem teste mapeado deve falhar.
3. Mudança com contrato completo deve retornar `SDD_OK`.
4. A repetição com a mesma entrada deve produzir a mesma decisão.
5. O Pre-PR Readiness deve registrar `sdd:contract` junto ao `head_sha` corrente.
