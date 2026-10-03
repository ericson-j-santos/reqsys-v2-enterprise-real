# Painel de projetos no acesso público DEV

## Objetivo

Disponibilizar, dentro do ReqSys autenticado, um acesso explícito ao painel já
existente de projetos e integrações sem duplicar telas ou quebrar endereços
anteriores.

## Critérios de aceite

1. O menu **Meu trabalho** apresenta o item **Painel de projetos**.
2. A rota `/painel-projetos` exige o recurso `dashboard:read` e apresenta a
   experiência Pulso, distinta da tela operacional de integrações.
3. A rota legada `/painel-integracao` continua funcionando.
4. A tela identifica claramente o acompanhamento de Planner, integrações,
   notificações e evidências.
5. O frontend compila e os testes de rota e navegação são aprovados.
6. A publicação ocorre somente em DEV pelo pipeline canônico do GitHub Pages.
7. O endereço público direto `/dev/painel-projetos/` encaminha para o ReqSys
   preservando `/painel-projetos` como destino depois do login Microsoft.
8. Destinos externos, recursivos ou inválidos não são aceitos no retorno do login.
9. A tela inicial apresenta, no topo e sem depender da expansão do menu lateral,
   um botão explícito **Abrir Painel de projetos** que leva à rota canônica.
10. O Pulso consolida somente dados retornados por ReqSys, Agile Runtime e
    rastreabilidade, vinculando-os por `requisito_id`, e mostra ambiente, origem,
    última sincronização, Planner, correlação e evidência quando disponíveis.
11. O panorama da saúde do portfólio expõe um nome acessível e não apresenta
    violações automatizáveis WCAG 2.2 A/AA no catálogo de rotas autenticadas.

## Fora de escopo

- alteração de APIs, dados, papéis ou permissões;
- promoção automática para HML ou PROD;
- criação de uma segunda aplicação independente do ReqSys.
