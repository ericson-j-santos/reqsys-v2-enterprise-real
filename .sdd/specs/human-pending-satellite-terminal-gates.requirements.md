# Human Pending Satellite — estado terminal e alta precisão

## Objetivo

O Human Pending Satellite deve notificar somente quando existir uma ação humana indispensável e atual. Estado histórico da issue, cabeçalhos genéricos ou frases vagas não podem gerar intervenção manual.

## Requisito 1 — intenção humana explícita

Cabeçalhos genéricos como `Responsável` e a frase isolada `evidência real` não constituem intenção humana. Falhas técnicas continuam sob responsabilidade do Coordinator.

## Requisito 2 — estado humano terminal

Comentários de OWNER, MEMBER ou COLLABORATOR podem registrar que um gate humano foi concluído e suprimir o alerta derivado do corpo histórico. Um comentário confiável posterior pode reabrir o gate quando surgir nova ação humana indispensável.

## Requisito 3 — controle explícito por labels

`human-gate:resolved` e `satellite:suppress-human` suprimem notificação. Outros labels `human-gate:*` são sinal explícito de gate humano ativo.

## Requisito 4 — entrada externa de negócio

Fonte SQL/DSN ou RDL/RDS corporativa e consulta/regra de negócio real devem permanecer classificáveis como dependência externa quando não puderem ser inferidas ou fabricadas pelo ReqSys. A notificação deve solicitar somente a referência/fonte e identidade de menor privilégio, sem pedir segredo em chat ou comentário.

## Critérios de aceite

1. Issue com apenas cabeçalho `Responsável` não é escalada.
2. Issue com apenas a expressão genérica `evidência real` não é escalada.
3. Aprovação humana futura/genérica não é escalada antes de existir gate atual explícito.
4. Dependência explícita de fonte SQL corporativa continua classificada como `external_business_input`.
5. Comentário confiável de gate concluído retorna estado `cleared`.
6. Comentário confiável posterior de nova ação humana retorna estado `active`.
7. Comentário não confiável não pode encerrar o gate.
8. Finding de fonte corporativa informa ambiente de integração externa, risco alto e ação sem exposição de segredo.
9. `tests/test_human_pending_satellite.py` permanece verde no HEAD exato.
