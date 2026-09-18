# RSM-01 — ServiceCase Domain — Requisitos

Issue: #1783

## Requisito 1 — contrato único de caso
O ReqSys deve representar `REQUEST`, `INCIDENT`, `PROBLEM` e `CHANGE` por um único contrato `ServiceCase`, evitando quatro máquinas de estado independentes.

## Requisito 2 — reutilização do catálogo existente
O catálogo persistido `ServicoTI` deve permanecer canônico. O RSM-01 não pode criar tabela concorrente de serviços; o domínio referencia o serviço por `service_id`.

## Requisito 3 — identidade e rastreabilidade
Cada caso deve possuir `case_id`, `correlation_id` e `idempotency_key`. A chave idempotente deve ser SHA-256 hexadecimal minúsculo e representar a identidade lógica que o RSM-02 usará para deduplicação persistida.

## Requisito 4 — prioridade determinística
Impacto e urgência devem produzir P1–P4 por regra determinística e testável, sem depender de IA ou infraestrutura externa.

## Requisito 5 — máquina de estados fail-closed
Somente transições presentes na matriz canônica podem ser executadas. Transição inválida deve lançar erro explícito e preservar o objeto original.

## Requisito 6 — contratos auxiliares mínimos
O incremento deve disponibilizar contratos mínimos de `Service`, `ServiceOffering`, `SlaPolicy`, `Approval`, `CaseEvent`, `ServiceDependency`, referências externas e evidências, sem acoplamento a FastAPI, SQLAlchemy, GitHub ou Teams.

## Critérios de aceite (Acceptance Criteria)
1. O contrato tipado e versionado expõe os quatro tipos de caso e os estados canônicos.
2. A matriz NEW → TRIAGE → IN_PROGRESS → RESOLVED → CLOSED é aceita.
3. CLOSED → IN_PROGRESS é rejeitada e o estado permanece CLOSED.
4. A matriz de prioridade cobre P1, P2, P3 e P4 de forma determinística.
5. Uma `idempotency_key` inválida é rejeitada.
6. Duas entradas com a mesma chave possuem a mesma `logical_identity`, preparando o replay idempotente do RSM-02.
7. Aprovação decidida sem timestamp com timezone é rejeitada.
8. Digest de evidência inválido e autodependência de serviço são rejeitados.
9. `backend/tests/test_service_management_domain.py` passa no HEAD exato.
10. Os testes existentes de Gestão de TI e Incidentes continuam passando.
11. O Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato antes da abertura de PR.
