# RSM-05 — Tela única do ServiceCase — Requisitos

Issue: #1787
Parent: #1782
Depende de: RSM-01 (#1783), RSM-02 (#1784), RSM-03 (#1785), RSM-04 (#1786)
Desbloqueia: RSM-06 (#1788)

## Requisito 1 — backend continua fonte autoritativa
A interface não deve codificar uma segunda máquina de estados. Cada representação de
`ServiceCase` devolvida pela API expõe `allowed_transitions`, calculado pelo domínio atual.
Guardas adicionais de aprovação/evidência continuam sendo validadas pelo backend.

## Requisito 2 — tela única
Uma única tela deve renderizar REQUEST, INCIDENT, PROBLEM e CHANGE pelo mesmo contrato,
sem componentes ou fluxos de estado paralelos por tipo.

## Requisito 3 — mutação sem falso sucesso
Após qualquer transição aceita, a interface deve reler o caso pela API e somente apresentar
sucesso quando o estado persistido relido coincidir com o alvo. Em erro 4xx/5xx, a interface
também relê o caso e preserva o estado autoritativo em vez de aplicar mutação otimista local.

## Requisito 4 — resolução exige evidência
Quando `RESOLVED` estiver entre as transições permitidas, a interface deve exigir URI de
evidência e SHA-256 válido antes de enviar a transição.

## Requisito 5 — E2E e leitura independente
O incremento deve executar o maior E2E de interface disponível. Testes de componente com
API simulada comprovam contrato visual, mas não substituem um E2E real de browser -> API ->
persistência -> leitura independente. Se o runtime de browser/persistência não estiver
disponível no SHA atual, a issue permanece parcialmente validada.

## Critérios de aceite
1. `GET /v1/service-cases/{case_id}` expõe `allowed_transitions` derivado do domínio.
2. A tela `/service-cases/:caseId?` atende os quatro tipos de caso.
3. Somente ações retornadas pelo backend são renderizadas.
4. Rejeição de uma ação pelo backend não produz mensagem de sucesso nem alteração local.
5. Transição aceita só produz sucesso após releitura da API confirmar o novo estado.
6. Resolução exige URI e SHA-256 antes do POST.
7. Testes backend e frontend cobrem caso positivo e controle negativo.
8. Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato antes da abertura da PR.
