# Protocolo de revalidação ReqSys 360

## Objetivo

Definir o critério mínimo para considerar o ReqSys 360 validado após avanço da branch `main`, evitando reutilização de evidência produzida para SHA anterior.

## Regra de fechamento

Uma issue de coerência ReqSys 360 só pode ser encerrada quando a evidência terminal pertencer ao mesmo SHA que está em `main` imediatamente antes do fechamento.

## Validação obrigatória

1. Capturar o SHA atual de `main`.
2. Executar o workflow `ReqSys 360 Coherence Gate` para esse estado.
3. Confirmar estado terminal `success`.
4. Confirmar que nenhum passo relevante ficou `skipped`.
5. Confirmar os testes de contrato de navegação sem falhas.
6. Confirmar `regression baseline` em estado `approved`, sem regressões acima do baseline e sem relaxamento de limites para obter aprovação.
7. Confirmar o E2E focado completo, incluindo o controle negativo de rota desconhecida.
8. Confirmar a publicação do artefato de evidência do mesmo run/SHA.
9. Reconsultar `main` imediatamente antes de encerrar a issue.
10. Se o SHA tiver avançado, invalidar a evidência terminal anterior para fins de fechamento e repetir a revalidação.

## Controle contra falso positivo

Não considerar como evidência terminal suficiente:

- run executado apenas em SHA anterior;
- run de PR cujo SHA validado seja somente o merge ref sintético;
- sucesso parcial com etapas relevantes ignoradas;
- artefato ausente ou pertencente a outro run/SHA;
- E2E incompleto;
- baseline aprovado após relaxamento não justificado de limites.

## Evidência mínima a registrar

- SHA final de `main`;
- ID e URL do run terminal;
- conclusão do workflow;
- resultado dos testes de contrato;
- estado e violações do baseline;
- resultado do E2E focado;
- nome e ID do artefato;
- confirmação de que o SHA de `main` permaneceu estável entre a validação e o fechamento.

## Rastreabilidade

Este protocolo foi adicionado durante a conclusão da issue #1633 para tornar explícito e repetível o critério de revalidação que já protege o ReqSys 360 contra evidências obsoletas e falsos positivos.
