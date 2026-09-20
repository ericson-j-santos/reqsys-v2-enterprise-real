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
14. `POST /v1/integracoes/figma-github/sync` deve exigir JWT admin ou service token com escopo `figma:sync`; chamadas anônimas devem retornar 401.
15. O workflow deve ser disparável apenas manualmente e pela rota exata allowlisted `/reqsys run figma-github-e2e-dev` na issue #1705.

## Critérios de aceite
1. O gate SDD reconhece este documento como contrato aprovado e todos os testes declarados em `sdd_gate.tests` existem.
2. O E2E falha fechado antes de qualquer mutação externa quando host, container, projeto, serviço ou SHA do runtime divergem do esperado.
3. A chamada anônima a `POST /v1/integracoes/figma-github/sync` retorna HTTP 401, enquanto JWT admin ou service token com escopo `figma:sync` autoriza o fluxo.
4. O controle negativo com `mode` inválido retorna HTTP 422 sem acessar Figma ou GitHub.
5. O caso positivo comprova por leitura independente o marker no issue GitHub e exatamente um comentário de retorno no Figma para o node `1:44`.
6. O replay da mesma entrada produz `created=0`, `updated=0`, `skipped>=2` e não duplica comentário de retorno no Figma.
7. Os defaults são carregados pelo Cofre sem alteração ou exposição de `FIGMA_ACCESS_TOKEN` e `GITHUB_TOKEN`; o token temporário de leitura é revogado no cleanup.
8. A evidência final pertence ao SHA exato testado, registra `production_touched=false` e não contém valores sensíveis.
