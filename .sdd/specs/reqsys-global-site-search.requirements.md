# Requisitos — busca global de telas do ReqSys (DEV)

## Problema
A aplicação ReqSys distribui telas por temas e subgrupos, mas não possui uma lupa global. As pesquisas atuais são restritas a algumas telas e o usuário precisa navegar manualmente para localizar a funcionalidade desejada.

## Correção mínima
Adicionar janela de busca rápida ao layout existente (desktop, menu recolhido e mobile), usando apenas o catálogo estático de rotas, títulos e descrições. Não criar endpoint, indexador de documentos internos, coleta de conteúdo do DOM, banco de busca externo ou privilégios novos.

## Critérios de aceite
1. Lupa acessível no menu principal, inclusive recolhido, e no cabeçalho móvel.
2. Atalho Ctrl+K/⌘K abre a busca; Enter abre a primeira tela encontrada; botão de fechar encerra sem navegar.
3. Termos com ou sem acentos e expressões como “planner teams” localizam telas pelas descrições do catálogo.
4. Destinos repetidos aparecem uma vez; telas não autorizadas e rotas inválidas não aparecem nem pela descrição.
5. Pesquisa vazia ou sem resultados oferece feedback claro.
6. A busca não lê registros de usuários/tenants, não consulta o backend e não substitui filtros específicos das telas; a autorização do router permanece obrigatória.
7. Rodar testes unitários positivos e negativos, Playwright de desktop, mobile, teclado e autorização, teste de regressão de navegação e build do frontend.
8. Abertura de PR exige READY_FOR_PR no SHA exato; merge exige todos os gates aplicáveis e mergeabilidade.
9. Publicação do frontend compilado em GitHub Pages /dev/ é independente da aprovação do PR e depende de autorização explícita. Realizar E2E real autenticado no ambiente publicado e verificação independente antes de declarar concluído.

## Evidência prevista
- frontend/src/utils/globalSearch.test.js: normalização, relevância, deduplicação, acesso e controle negativo.
- frontend/tests/e2e/global-search.spec.js: fluxo de busca e navegação no navegador, inclusive dispositivo móvel e permissão.
- CI Pre-PR Readiness Gate vinculado ao HEAD da branch.
- Deploy governado e E2E real no GitHub Pages /dev/ após autorização de publicação.
