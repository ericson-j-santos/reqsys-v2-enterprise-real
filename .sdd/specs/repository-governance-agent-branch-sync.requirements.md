# Repository Governance Agent — sincronização de branches

## Objetivo

Eliminar o retrabalho recorrente causado por PRs que ficam atrás da `main` após outro merge, mantendo a fila governada como única rota de integração na `main`.

## Classificação

`hotfix`.

## Requisitos

1. A cada `push` na `main`, o agente deve inspecionar PRs abertas cuja base seja `main`.
2. O agente só pode atualizar branches pertencentes ao próprio repositório; forks externos devem ser ignorados.
3. PRs em draft são ignoradas por padrão; a única exceção é PR same-repo com `ci:recuperado`, que pode ter somente a branch sincronizada. Conflito, mergeabilidade desconhecida ou mudança de estado/SHA continuam bloqueando.
4. A decisão de atualização deve usar `behind_by > 0` contra o SHA de base relido imediatamente antes da mutação.
5. A sincronização deve preservar proteção equivalente a compare-and-swap: HEAD e base são relidos pela API e confirmados novamente no Git remoto antes de criar o commit; o push deve ser não-forçado, de modo que avanço concorrente da branch rejeite a escrita em vez de sobrescrevê-la.
6. A sincronização Git deve operar em repositório `bare`, usando `merge-tree --write-tree` e `commit-tree`; não pode fazer checkout nem executar código controlado pela branch do PR.
7. O commit de sincronização deve ter como primeiro parent o HEAD esperado da PR e como segundo parent o SHA observado da `main`.
8. Após o push, o agente deve reler o PR e comprovar novo HEAD contendo a base observada com `behind_by=0`.
9. Ausência de confirmação funcional deve falhar o job; código de saída zero isolado não é sucesso.
10. O fan-out geral máximo continua em 3 PRs; quando existir `ci:recuperado`, selecionar somente a PR recuperada mais antiga por número para avanço serial.
11. O agente não pode integrar PR na `main`, executar deploy/promoção, force-push, alterar segredo ou branch protection.
12. O `Governed Merge Queue` e o `Governed PR Automation` continuam responsáveis pela validação e pela integração depois que os gates do novo HEAD ficarem verdes.
13. O `GITHUB_TOKEN` nativo deve permanecer somente leitura (`contents: read`, `pull-requests: read`) e ser usado apenas para observação. A escrita deve usar token temporário da GitHub App governada `REQSYS_STACK_REBASE_APP_ID`/`REQSYS_STACK_REBASE_PRIVATE_KEY`, solicitando somente `contents: write`; não pode solicitar `pull-requests: write`, usar PAT ou usar o `GITHUB_TOKEN` como fallback de escrita.
14. O self-sync deve usar `pull_request_target`, executando a definição confiável da `main`; o repositório Git efêmero deve ser `bare`, sem checkout da branch candidata.
15. Execuções concorrentes devem usar lane determinística e cancelar execução obsoleta.
16. Para **sincronização elegível** (`behind_by > 0` e demais controles aprovados), ausência da configuração da GitHub App ou incapacidade de emitir `contents: write` deve falhar fechado antes de qualquer mutação.
17. Ambos os jobs devem executar pré-admissão **somente leitura antes do token de escrita**, sem checkout, contendo identidade same-repo, estado draft/`ci:recuperado`, mergeabilidade, SHA base corrente e `behind_by`. PR sem sincronização elegível deve encerrar com `noop`/aviso sem validar segredo ou pedir token. Erro/ausência de comparação deve falhar fechado; verificação de estado/HEAD/base deve ser refeita imediatamente antes da escrita.

## Controles negativos

- PR `behind_by=0`, draft sem `ci:recuperado`, fork e conflito: **nenhum token solicitado**, sem mutação nem falso erro de identidade;
- comparação de SHA indisponível: pré-admissão falha fechada sem chamar a App;
- PR elegível e App sem instalação/permissão: falha de autenticação **não** é mascarada, sem fallback para `GITHUB_TOKEN`;
- teste de regressão deve falhar se remover o guarda de emissão de token (test-of-test);

- draft sem `ci:recuperado` => não atualiza; draft com `ci:recuperado` pode ser sincronizado, mas nunca integrado na `main` por este agente;
- fork externo => não atualiza;
- conflito => não atualiza;
- mergeabilidade desconhecida => não atualiza;
- HEAD mudou entre a leitura da API e a leitura Git => `stale_noop`;
- `main` mudou entre a leitura da API e a leitura Git => `stale_noop`;
- HEAD avançou antes do push => push não-forçado é rejeitado; a releitura classifica `stale_noop` e nenhum trabalho concorrente é sobrescrito;
- push falha sem mudança concorrente => `git_push_failed` e job vermelho;
- conflito detectado por `merge-tree` => `git_merge_tree_conflict`, sem escrita;
- orçamento de 3 atualizações esgotado => `deferred`;
- uso do `GITHUB_TOKEN` para a escrita continua inválido: o E2E anterior mostrou HTTP 403 e, com ampliação, SHAs criados pelo `github-actions[bot]` produziram workflows `action_required`;
- GitHub App ausente ou sem `contents: write` => falha antes da mutação;
- push aceito, mas leitura independente não comprova a base observada como ancestral do novo HEAD => job falha;
- nenhum caminho chama API de merge de Pull Request ou escreve em `refs/heads/main`.

## Critérios de aceite

- a pre-admissão de ambos os jobs executa antes do token, com 20 simulações positivas/negativas e controle de API indisponível; o token só pode ser gerado em caso `eligible=true`;
- o PR gate deve validar o contrato SDD alterado no SHA final, além de YAML, Python, regressão e segurança;

- `tests/test_repository_governance_agent.py` verde;
- SDD Gate verde no HEAD final;
- CI do PR verde no HEAD atual;
- `GITHUB_TOKEN` nativo permanece somente leitura;
- token de mutação é emitido pela GitHub App já governada com apenas `contents: write`;
- o workflow não solicita `pull-requests: write`;
- nenhuma credencial de escrita é persistida em URL Git; a autenticação do push usa header mascarado no processo;
- após integração deste hotfix, o `push` da própria `main` dispara o agente;
- se houver PR segura atrasada, leitura independente observa novo HEAD contendo o SHA de base capturado e `behind_by=0`;
- o novo SHA produzido pela GitHub App dispara workflows do PR normalmente, sem `action_required`;
- repetição quando `behind_by=0` é idempotente e não cria novo commit;
- avanço concorrente do HEAD antes do push não é sobrescrito;
- PR com gate pendente pode ter branch sincronizada, mas não pode ser integrada na `main` por este agente;
- leitura independente confirma que nenhuma PR foi integrada pelo `Repository Governance Agent`;
- nenhuma ação de deploy/promoção é executada.

## Extensão de validação técnica por processo independente — 23/11/2026

- **Classificação:** capacidade adicional ausente no fluxo existente (review automatizado por SHA antes de eventual merge), solicitada pelo proprietário. Não substituir a revisão/identidade do Validator por comentário do autor.
- **Reuso:** `.github/workflows/pr-quality-review.yml` (não criar outro workflow/serviço), acionado por `pull_request` somente quando houver mudanças no agente de sincronização ou nos seus testes; despacho manual pré-existente preservado.
- **Admissão:** PR aberta, same-repo, base main/head atuais lidos pela API; dois checkouts em diretórios distintos por SHAs completos; `GITHUB_TOKEN` somente leitura na validação e nas releituras.
- **Execução:** revisão de risco por script preexistente da main (rejeitar fallback sem HEAD real), pytest da candidata, controle negativo que exige falha com o workflow anterior, digest SHA-256 do recibo em artifact de 30 dias, segunda execução isolada conferindo hash e HEAD/base ao vivo.
- **Limites:** resultado `TARGETED_TECHNICAL_VALIDATION_PASSED` só comprova esses testes. Não libera merge/deploy, não assina parecer humano e não prova sincronização real da GitHub App (E2E pós-integração ainda pendente).
- **Aceite deste incremento:** ambos os jobs executados em runners GitHub separados, artifact gerado e relido, HEAD exato do candidato confirmado, casos positivo/negativo e repetição cobertos, nenhuma escrita em main. Se qualquer precondição falhar, falhar fechado.
- **Custo:** executor GitHub-hosted padrão em repositório público, sem novos serviços. Nenhuma autorização de cota paga, segredos ou ações administrativas.
