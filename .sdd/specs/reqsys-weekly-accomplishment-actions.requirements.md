# Log semanal de realizações do ReqSys via GitHub Actions

## Objetivo
Substituir o agendamento recorrente do chat para o log semanal do ReqSys por uma execução auditável no GitHub Actions, usando somente evidências verificáveis do próprio repositório.

## Requisito 1 — agendamento
O workflow deve executar às sextas-feiras às 09:00 no horário de São Paulo, representado por 12:00 UTC, e também permitir execução manual.

## Requisito 2 — evidência
O relatório deve usar apenas Pull Requests mescladas, SHAs, arquivos alterados e checks obtidos pela API do GitHub. Ausência de evidência não pode ser convertida em conclusão positiva.

## Requisito 3 — dimensões
Cada item deve separar explicitamente: implementado, validado, evidenciado, consolidado e governado. Os critérios usados para cada dimensão devem aparecer no relatório.

## Requisito 4 — percentuais
Percentuais devem representar cobertura de evidência dentro da janela analisada. É proibido apresentá-los como percentual global de conclusão do ReqSys.

## Requisito 5 — comparação
Quando existir artifact anterior do mesmo workflow, o relatório deve comparar as contagens atuais com o log anterior. Na primeira execução, deve registrar explicitamente a ausência de baseline anterior.

## Requisito 6 — rastreabilidade
A saída deve conter Markdown e JSON, links para PRs, SHAs analisados, janela temporal e itens que ainda precisam de evidência.

## Critérios de aceite (Acceptance Criteria)
1. O workflow contém `schedule` para sexta-feira às 12:00 UTC e `workflow_dispatch`.
2. O job roda em runner hospedado pelo GitHub, sem `self-hosted`, sem acesso aos PCs e sem segredos externos.
3. O gerador classifica as cinco dimensões com regras determinísticas e falha explicitamente em erros de API.
4. Checks ausentes ou falhos impedem `validated=true`; falta de link/check impede `evidenced=true`.
5. O relatório identifica percentuais como cobertura de evidência, não progresso global.
6. A repetição com a mesma entrada produz as mesmas classificações.
7. Testes positivos, negativos e de comparação anterior passam.
8. O Pre-PR Readiness deve aprovar o HEAD exato antes da abertura da Pull Request.
