# Retorno Microsoft resiliente em navegador móvel embutido

## Objetivo

Concluir o login Microsoft quando Safari ou um navegador embutido retornar ao ReqSys em um novo contexto de `sessionStorage`, sem reduzir as validações de PKCE e `state`.

## Critérios de aceite

- Respostas OAuth em query ou fragmento são consumidas antes do guard de rotas.
- Somente o estado temporário necessário do MSAL é transferido entre contextos; tokens não são copiados para `localStorage`.
- O handoff é vinculado ao `clientId`, expira em até dez minutos e é consumido uma única vez.
- `state`, nonce e PKCE continuam validados pelo MSAL antes da emissão da sessão ReqSys.
- Falhas de cache ou `state` permanecem visíveis quando ocorrerem no callback.
- A URI Pages canônica coincide com o callback anunciado pelo backend.
- Redirecionamentos após HTTP 401 preservam o prefixo do GitHub Pages.

## Evidência operacional

Na tentativa real de 2 de outubro de 2026, o Entra registrou sucesso e MFA concluída no iPhone, mas nenhum `POST /v1/auth/azure` chegou ao backend. A mudança do `correlation_id` entre ida e retorno confirmou a troca de contexto de `sessionStorage`.
