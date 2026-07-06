# UX de uso real do ReqSys

## Decisão

O ReqSys deve priorizar a jornada diária do analista e esconder detalhes técnicos da tela principal. Workflows, CI, ambientes, runtime e correlation_id continuam disponíveis como evidência operacional, mas deixam de competir visualmente com o trabalho principal.

## Jornada canônica

1. Entrada da demanda.
2. Refinamento do requisito.
3. Critérios de aceite e BDD.
4. Aprovação ou devolução.
5. Rastreabilidade de origem, decisão, responsável e evidência.
6. Exportação para relatório, Redmine, GitHub ou governança.

## Itens priorizados na interface

- Nova demanda.
- Workspace operacional.
- Fila de pendências.
- Requisitos com baixa qualidade.
- Histórias sem critério de aceite.
- Itens sem rastreabilidade.
- Aprovações pendentes.
- Qualidade das informações.

## Itens removidos da jornada principal

- Detalhes de CI/CD.
- Portas e ambientes técnicos.
- Build e SHA como informação primária.
- Artefatos de runtime sem ação direta para o analista.
- Histórico técnico de incrementos.

## Evidência preservada

A tela mantém evidência discreta com versão, ambiente, correlation_id, telemetria de jornada e política de ausência de dado sensível. Esses dados devem apoiar auditoria e suporte, não conduzir a experiência primária.

## Próximos incrementos recomendados

1. Conectar a fila de trabalho aos dados reais da API.
2. Criar filtros persistentes por status, área, responsável e qualidade.
3. Adicionar score real de prontidão do requisito.
4. Permitir exportação governada para Redmine/GitHub/relatório.
5. Validar fluxo com teste E2E de cadastro, refinamento, aprovação e rastreabilidade.
