# ADR-021 — Retorno Figma/GitHub em tela

## Status

Proposto

## Contexto

O ReqSys já possui backend de integração Figma/GitHub para sincronização e consulta de status. Faltava uma experiência visual dentro da aplicação para executar a sincronização e consultar o retorno operacional em tela.

## Decisão

Criar uma tela dedicada em `/figma-github`, consumindo os endpoints existentes:

- `POST /v1/integracoes/figma-github/sync`
- `GET /v1/integracoes/figma-github/status`

A tela deve apresentar:

- formulário de sincronização;
- retorno da última execução;
- cards de resumo;
- tabela analítica;
- filtro por status;
- links para issues GitHub;
- tratamento de erro;
- responsividade.

## Consequências positivas

- Usuário passa a ter retorno visual direto da integração.
- Reduz dependência de inspeção manual de API.
- Fortalece rastreabilidade entre design, requisitos e execução GitHub.
- Abre caminho para drill-down e arquitetura viva integrada ao Figma.

## Consequências negativas / riscos

- A tela depende da disponibilidade dos endpoints de backend.
- Sem configuração Figma/GitHub no ambiente, o sync pode retornar erro governado.
- O item de menu ainda precisa ser atualizado em `AppLayout.vue`; a tentativa foi bloqueada pelo conector nesta execução.

## Gates

- Não publicar em produção sem CI verde.
- Não marcar PR como ready for review sem build frontend e validação E2E.
- Não expor tokens, file secrets ou credenciais no frontend.
- Manter PR em draft enquanto houver pendência de menu, rebase ou CI.

## Ambiente

- Implementação aplicada em branch de feature.
- Produção protegida; sem merge/deploy automático nesta etapa.
