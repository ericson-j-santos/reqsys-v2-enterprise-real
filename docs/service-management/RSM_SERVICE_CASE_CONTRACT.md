# RSM-01 — contrato de domínio ServiceCase

Issue: #1783  
Contrato: `rsm-service-case-v1`  
`schema_version`: `1.0.0`

## Decisão Pareto

O catálogo persistido já existente, `ServicoTI` (`gestao_ti_servicos`), continua sendo a fonte canônica dos serviços.
O RSM não cria uma segunda tabela de serviços neste incremento. O contrato `Service` é uma visão de domínio
para desacoplar regras de negócio de SQLAlchemy/FastAPI e permitir adaptadores posteriores.

A rota atual `/v1/incidentes` é preservada. Ela representa uma visão de incidentes baseada em requisitos e não é
promovida implicitamente a fonte canônica de casos ITSM.

## Tipos de caso

- `REQUEST`
- `INCIDENT`
- `PROBLEM`
- `CHANGE`

Todos compartilham o mesmo `ServiceCase`. Especializações futuras devem compor esse contrato em vez de criar
máquinas de estado independentes.

## Identidade

- `case_id`: UUID da ocorrência.
- `service_id`: UUID do `ServicoTI` canônico.
- `correlation_id`: rastreabilidade ponta a ponta.
- `idempotency_key`: SHA-256 hexadecimal minúsculo de 64 caracteres.
- `logical_identity`: igual à `idempotency_key`; será usada pelo repositório do RSM-02 para deduplicação.

Dois objetos podem possuir `case_id` diferentes durante validação de entrada, mas a mesma
`logical_identity` identifica a mesma solicitação lógica. A persistência do RSM-02 deverá convergir o replay.

## Prioridade determinística

Pesos de impacto e urgência:

| Nível | Peso |
| --- | ---: |
| LOW | 1 |
| MEDIUM | 2 |
| HIGH | 3 |
| CRITICAL | 4 |

A soma produz:

| Soma | Prioridade |
| ---: | --- |
| 7–8 | P1 |
| 5–6 | P2 |
| 3–4 | P3 |
| 2 | P4 |

Não há classificação por IA nessa regra; para a mesma entrada o resultado deve ser sempre o mesmo.

## Estados e transições

| Origem | Destinos permitidos |
| --- | --- |
| NEW | TRIAGE, CANCELED |
| TRIAGE | PENDING_APPROVAL, IN_PROGRESS, CANCELED |
| PENDING_APPROVAL | TRIAGE, IN_PROGRESS, CANCELED |
| IN_PROGRESS | PENDING_EXTERNAL, RESOLVED, CANCELED |
| PENDING_EXTERNAL | IN_PROGRESS, RESOLVED, CANCELED |
| RESOLVED | IN_PROGRESS, CLOSED |
| CLOSED | nenhum |
| CANCELED | nenhum |

Transição fora da matriz lança `InvalidStateTransition` e não modifica o objeto original.

## Contratos auxiliares

- `Service`: visão do `ServicoTI`, sem persistência duplicada.
- `ServiceOffering`: oferta vinculada por `service_id`.
- `SlaPolicy`: metas de resposta e resolução; resolução nunca pode ser menor que resposta.
- `Approval`: decisão auditável; APPROVED/REJECTED exigem timestamp com timezone.
- `CaseEvent`: evento com UUID, `correlation_id`, timestamp com timezone e versão do esquema.
- `ServiceDependency`: relação tipada entre serviços; autorreferência é bloqueada.
- `EvidenceReference`: referência externa; digest, quando fornecido, deve ser SHA-256 válido.

## Limites deste incremento

Não há tabela, migração, endpoint, fila ou integração externa nova no RSM-01. Persistência/API/eventos idempotentes
são responsabilidade do RSM-02 (#1784). Catálogo/ofertas executáveis ficam no RSM-03 (#1785).

## Validação

O teste de contrato deve comprovar:

1. cálculo determinístico de P1–P4;
2. criação válida e identidade lógica estável para replay;
3. caminho NEW → TRIAGE → IN_PROGRESS → RESOLVED → CLOSED;
4. tentativa CLOSED → IN_PROGRESS falha e preserva CLOSED;
5. chave de idempotência inválida falha;
6. aprovação decidida sem timestamp falha;
7. digest de evidência inválido falha;
8. dependência de serviço para si mesmo falha.

Como o RSM-01 não possui persistência, leitura independente de banco não se aplica neste incremento. O RSM-02
deverá adicionar persistência, leitura independente, concorrência e replay sem duplicidade.
