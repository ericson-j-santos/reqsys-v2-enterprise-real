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

## Incremento: workspace operacional com dados reais

A tela principal passa a consumir `GET /api/requisitos/workspace` como fonte primária para métricas, fila de trabalho e score médio de prontidão.

### Contrato operacional

- `metrics`: cartões de prontidão, qualidade, workflow e pendências.
- `action_queue`: fila consolidada do analista.
- `summary`: totais, score médio e distribuição por status.
- `top_items`: itens com menor prontidão para priorização.
- `filters`: filtros aplicados por status, área e responsável.

### Filtros persistentes

O frontend persiste filtros operacionais em `localStorage` com a chave `reqsys.workspace.filters`, preservando status, área e responsável entre navegações sem exigir autenticação ou backend adicional.

### Fallback seguro

Se a API estiver indisponível, a interface mantém valores de fallback e exibe evidência visual `dados fallback`, evitando bloquear a jornada do usuário final.

## Itens removidos da jornada principal

- Detalhes de CI/CD.
- Portas e ambientes técnicos.
- Build e SHA como informação primária.
- Artefatos de runtime sem ação direta para o analista.
- Histórico técnico de incrementos.

## Evidência preservada

A tela mantém evidência discreta com versão, ambiente, correlation_id, telemetria de jornada e política de ausência de dado sensível. Esses dados devem apoiar auditoria e suporte, não conduzir a experiência primária.

## Próximos incrementos recomendados

1. Substituir heurística de score por critérios persistidos de aceite, BDD e rastreabilidade.
2. Criar endpoint de transição governada do workflow: entrada, refinamento, aprovação, evidência e exportação.
3. Adicionar filtros visuais editáveis por status, área e responsável.
4. Permitir exportação governada para Redmine/GitHub/relatório.
5. Validar fluxo com teste E2E de cadastro, refinamento, aprovação e rastreabilidade.
