# Figma ↔ GitHub E2E DEV governado

## Objetivo
Configurar os defaults da integração Figma/GitHub apenas no runtime DEV PC24x7 e comprovar o ciclo real com leitura independente e replay idempotente.

## Requisitos
1. Executar somente em `DESKTOP-PDQK954` no runner `[self-hosted, Windows, X64, pc24x7, reqsys-dev]`.
2. Falhar antes de qualquer mutação se o container não for `wt-pc24x7-piloto-api-1`, o projeto/serviço divergirem ou o `GITHUB_SHA` do runtime não for o SHA exato do workflow.
3. Confirmar que `/v1/auth/config` identifica DEV e permite o login demo administrativo usado pelos E2Es locais existentes.
4. Exigir Cofre inicializado.
5. Gravar somente os defaults `FIGMA_DEFAULT_FILE_KEY` e `FIGMA_GITHUB_DEFAULT_REPO`; não alterar `FIGMA_ACCESS_TOKEN` nem `GITHUB_TOKEN`.
6. Validar a existência das credenciais Figma/GitHub com token temporário escopado do Cofre, sem publicar os valores.
7. Reiniciar somente o container API DEV para recarregar os defaults.
8. O controle negativo deve usar `mode` inválido e receber HTTP 422 antes de acesso externo.
9. O positivo deve sincronizar somente o node `1:44` do arquivo canônico, sem ler comentários Figma como entradas.
10. A leitura independente deve comprovar o marker no issue GitHub e exatamente um comentário de retorno no Figma.
11. O replay deve produzir `created=0`, `updated=0`, `skipped>=2` e manter exatamente um comentário de retorno.
12. O token temporário do Cofre deve ser revogado em cleanup.
13. Nenhum segredo deve ir para artifact/log e `production_touched=false`.
14. `POST /v1/integracoes/figma-github/sync` deve exigir JWT admin ou service token com escopo `figma:sync`; chamadas anônimas devem retornar 401.\n15. O workflow deve ser disparável apenas manualmente e pela rota exata allowlisted `/reqsys run figma-github-e2e-dev` na issue #1705.
