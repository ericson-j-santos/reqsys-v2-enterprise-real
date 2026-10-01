# Cutover app-only das conexões Microsoft — Requisitos

## Objetivo

Conectar o painel ReqSys às fontes Microsoft em andamento por um backend autenticado,
com identidades dedicadas por ambiente e sem expor tokens ou segredos ao navegador.

## Requisitos

1. Power Platform, Dataverse e SharePoint devem usar client credentials dedicadas.
2. DEV, HML e PROD devem manter identidades, URLs e segredos separados.
3. Dataverse deve usar Application User habilitado com o papel `ReqSys Workflow Reader`.
4. SharePoint deve usar `Sites.Selected` e concessão `read` somente no site configurado.
5. O registro de governança pode conter identificadores e referências, nunca valores de segredo.
6. Os workflows devem aplicar os materiais ao Fly em uma única operação por ambiente.
7. Falhas OAuth devem retornar somente códigos e metadados sanitizados.
8. Endpoints públicos devem acessar Microsoft apenas pelo backend autenticado.
9. Cada item deve preservar ambiente, origem, última sincronização e link de evidência quando disponível.
10. A promoção deve seguir DEV, HML e PROD, com gates de aprovação existentes.
11. O smoke pré-deploy deve funcionar mesmo quando o runtime ainda estiver na imagem anterior.
12. A ausência de qualquer material obrigatório deve falhar fechado.

## Critérios de aceite

- Testes direcionados de OAuth, Dataverse, SharePoint e contrato de secrets são aprovados.
- O catálogo canônico contém bindings para todos os materiais requeridos nos três ambientes.
- O app SharePoint DEV obtém token e lê a lista `IA_Catalogo_Projetos` no site selecionado.
- O workflow DEV confirma as variáveis no Fly e aprova os smokes Power Platform e Dataverse.
- Nenhuma resposta operacional ou log contém client secret ou access token.
- Actions externas dos workflows modificados ficam fixadas por SHA imutável.
- HML e PROD só são promovidos após o sucesso do ambiente anterior e seus gates próprios.
