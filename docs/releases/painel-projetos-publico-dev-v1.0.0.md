# Painel de projetos no acesso público DEV v1.0.0

## Resumo

O painel já existente de projetos e integrações passa a ser acessível pela rota
`/painel-projetos` e pelo item **Painel de projetos** na área **Meu trabalho** do
ReqSys. A rota legada `/painel-integracao` foi preservada.

## Escopo

- acesso autenticado pelo mesmo login Microsoft do ReqSys;
- acompanhamento consolidado de Planner, integrações, notificações e evidências;
- publicação somente em DEV pelo pipeline canônico do GitHub Pages.

## Evidência de validação

- testes focados do catálogo de navegação e contrato da rota;
- build de produção do frontend;
- smoke autenticado da rota pública após a publicação.

## Risco e rollback

O ajuste não altera APIs, dados ou permissões. O rollback consiste em remover o
alias e o item de navegação, mantendo a rota legada intacta.
