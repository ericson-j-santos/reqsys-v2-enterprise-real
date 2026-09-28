# Painel central vivo do ciclo ReqSys

## Objetivo

Eliminar o estado operacional estático do painel de acompanhamento e transformá-lo
em uma projeção atual, rastreável e fail-closed das fontes oficiais usadas no
ecossistema ReqSys.

O painel deve consolidar GitHub/PR/CI, saúde da projeção do TODO Global,
certificação Microsoft Teams, evidências do Runtime PC24x7, Power BI e demais
repositórios operacionais configurados, sem transformar o dashboard em nova
fonte canônica.

## Requisitos

1. O estado publicado deve ser gerado em tempo de execução pelo workflow e conter
   o SHA e o run que produziram a evidência.
2. Dados de repositórios devem vir da API GitHub; fonte inacessível deve aparecer
   como `unavailable` ou `partial`, nunca como sucesso inferido.
3. O TODO Global deve aparecer somente como saúde de projeção/reconciliação.
   O painel deve declarar explicitamente que não substitui a fonte canônica.
4. A certificação Teams deve reutilizar o contrato já produzido pelo workflow
   `Teams Notification Dashboard`, sem duplicar lógica de SLO.
5. Runtime PC24x7 deve exibir evidências de workflows relevantes sem considerar
   workflow verde como prova física same-SHA quando esse critério for exigido.
6. Repositórios privados devem ser lidos, quando disponível, por token temporário
   somente leitura da GitHub App já existente. Falha de acesso não pode derrubar
   a projeção de outras fontes.
7. O HTML público não deve carregar frameworks/CDNs nem conter segredos ou
   credenciais.
8. O estado versionado no repositório deve ser apenas bootstrap/fallback sem
   números de PR, percentuais ou estados operacionais congelados.
9. O painel detalhado do Teams deve permanecer disponível separadamente, para
   preservar compatibilidade e investigação operacional.
10. A publicação em GitHub Pages continua separada da implementação e exige o
    gate/autorização existente; esta mudança não deve disparar deploy.
11. O produtor deve executar também após um merge realizado pelo `Governed PR Automation`,
    mesmo quando o `GITHUB_TOKEN` do merge não gerar um novo evento `push`, e deve
    vincular `source.sha` ao SHA realmente presente no checkout da `main`.

## Critérios de aceite

1. O teste unitário comprova coleta de SHA, PR aberto e último CI a partir de uma
   fonte GitHub simulada.
2. O controle negativo comprova que repositório inacessível é marcado
   `unavailable` sem inventar SHA, PR ou estado de CI.
3. O teste comprova que TODO Global é rotulado como `projection_health` e mantém
   `canonical_source=TODO Global`.
4. O validador do painel reprova regressão para JSON operacional embutido/estático
   e exige referência ao contrato `global-status.json`.
5. O workflow produtor gera e valida `global-status.json`, preserva
   `data.json` e `certification-status.json` do Teams e mantém o detalhe Teams
   em `/teams/`.
6. O deploy composto apenas empacota a nova saída; nenhuma execução de deploy é
   feita por este incremento.
7. O Pre-PR Readiness Gate deve retornar `READY_FOR_PR=passed` no HEAD exato e
   `behind_by=0` antes da abertura da PR.
8. Após merge, uma execução nova do produtor deve gerar evidência no SHA corrente.
   Até essa execução ocorrer, o estado funcional permanece parcial.
9. O gatilho `workflow_run` deve aceitar apenas conclusão `success` do caminho de
   auto-merge do `Governed PR Automation` e não deve conceder permissão de deploy.
10. O `global-status.json` produzido deve registrar como `source.sha` o SHA do
    checkout da `main`, não o SHA do workflow que disparou o evento.
