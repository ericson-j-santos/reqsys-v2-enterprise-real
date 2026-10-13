# ReqSys — E2E público da busca global (somente DEV)

## Objetivo
Comprovar o carregamento do frontend publicado no GitHub Pages /dev/ e, quando houver sessão Microsoft válida autorizada, a interação real com a lupa sem mocks.

## Critérios de aceite
1. Browser sem sessão acessa a entrada Pages estável e exibe login Microsoft, mas não a lupa protegida nem login demo.
2. O bundle de produção é carregado do caminho /reqsys-v2-enterprise-real/dev/assets/ e contém controles desktop, mobile e diálogo de busca.
3. A validação HTTP do locator DEV resolve somente HTTPS *.trycloudflare.com, comprova SHA observado e exige demo_login_enabled=false e azure_enabled=true.
4. workflow_dispatch exige expected_published_sha completo; divergência com a API pública deve bloquear.
5. No modo autenticado, o segredo MSAL pré-existente só pode ser consumido dentro do runner DEV. Sessão ausente, expirada, de outra origem ou sem POST real /api/v1/auth/azure=200 deve falhar, nunca passar via skip.
6. Depois do login real, testar Rastreabilidade, clique e rota, Ctrl+K/Enter, consulta inexistente e cabeçalho móvel sem interceptação de API.
7. Não enviar tokens, cookies, storage state ou capturas autenticadas a artefatos/Issues; nunca habilitar login demo nem promover HML/PROD.
8. Public smoke verde não substitui aceite autenticado, especialmente o controle RBAC com identidade de privilégios restritos.
9. Mudanças de teste apenas via PR governada, Pre-PR Readiness no SHA exato e CI completo; nenhuma publicação de ambiente autorizada por este incremento.

## Evidências
- frontend/tests/e2e/global-search-published.spec.js
- .github/workflows/validacao-acessos.yml
- Run público independente vinculado a main implantada e ao bundle servido.
- Run autenticado apenas quando houver sessão delegada Microsoft válida e autorizado seu uso.

## Complemento de homologação — 13/10/2026

10. No `workflow_dispatch`, executar o navegador anônimo mesmo se a validação do runtime falhar por `build_sha_mismatch`, para manter evidência independente do Pages; o workflow completo deve continuar reprovado enquanto o runtime estiver defasado.
11. O job autenticado depende **dos dois** jobs, `validar-acessos` e `anonymous`, aprovados na mesma run; qualquer falha, ausência ou cancelamento bloqueia sua execução, sem usar `always()` para contornar o SHA.
12. A única imagem persistida deve ser `public-login.png` do navegador anônimo, gerada após comprovar login Microsoft visível, ausência de demo e de lupa protegida; não capturar sessão, cookie ou token autenticado.
13. Incluir regressões preventivas para dependência entre jobs, execução anônima independente, limites dos artefatos e mecanismos fail-closed, com E2E público no maior escopo disponível e controle negativo.
