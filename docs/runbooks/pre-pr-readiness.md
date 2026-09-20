# Pre-PR Readiness Gate

## Objetivo

Reduzir retrabalho de CI deslocando para a branch, antes da abertura da Pull Request, falhas determinísticas que podem ser verificadas sem depender do contexto da PR.

## Estados

- `READY_FOR_PR=passed`: o HEAD atual passou pelas verificações mínimas pré-PR e pode seguir para abertura de PR.
- `READY_FOR_PR=blocked`: a PR não deve ser criada para esse HEAD; corrigir a causa e aguardar uma nova execução verde.
- `READY_FOR_MERGE`: permanece responsabilidade dos gates completos da PR, E2E aplicável, revisões e mergeabilidade.

`READY_FOR_PR` não substitui `READY_FOR_MERGE`.

## Regra operacional

1. Trabalhar em branch/worker isolado.
2. Commitar o incremento.
3. O `Pre-PR Readiness Gate` executa automaticamente em `push` de qualquer branch diferente de `main`.
4. A evidência deve referenciar exatamente o `head_sha` atual.
5. Se a `main` avançar e a branch ficar atrás, o gate falha fechado até a branch ser reconciliada.
6. Agentes e automações devem abrir PR somente depois de uma execução `success` do `Pre-PR Readiness Gate` no HEAD atual.
7. Qualquer novo commit invalida a evidência anterior e exige nova execução.
8. Depois da abertura da PR, os gates completos continuam obrigatórios; um `READY_FOR_PR=passed` não autoriza merge.
9. A Governed Merge Queue exige também `Pre-PR Readiness Gate=success` no HEAD exato; ausência ou falha bloqueia publicação na `main`.

## Enforcement v2 — caminhos de abertura de PR

A regra deixou de ser apenas documental e passou a ser aplicada nos dois caminhos canônicos de abertura de PR:

### Autoabertura por agente

`scripts/auto_open_agent_pr.py` consulta a API do GitHub antes de criar uma PR nova e exige:

- run do workflow `Pre-PR Readiness Gate` para o mesmo `GITHUB_SHA`;
- evento `push`;
- execução `completed` com `conclusion=success`;
- `main` corrente como ancestral do HEAD;
- `behind_by=0`;
- branch estritamente à frente da base, com `ahead_by>0`.

O workflow pode iniciar em paralelo com o Pre-PR Readiness; por isso o autoabridor aguarda com limite configurável (`READY_FOR_PR_WAIT_SECONDS`, padrão 600 s) e polling controlado (`READY_FOR_PR_POLL_SECONDS`, padrão 5 s). Se a evidência não aparecer ou não ficar verde dentro do limite, nenhuma chamada de criação de PR é executada.

O resultado é registrado em:

- `artifacts/auto-pr-request/ready-for-pr-verification.json`;
- `artifacts/auto-pr-request/auto-pr-request.json`.

Quando bloqueado, `auto-pr-request.json` usa `status=blocked_readiness`.

### Abertura governada manual/agente

`scripts/criar-pr-governado.sh` preserva seus preflights existentes e, imediatamente antes de `gh pr create`, executa `scripts/pre_pr_readiness.py`. O script revalida o artifact gerado e exige simultaneamente:

- `status=passed`;
- `head_sha` igual ao `git rev-parse HEAD` atual;
- `base_ref` igual à base solicitada;
- `base_sha` igual ao `origin/<base>` atual após o fetch;
- `behind_by=0`.

Qualquer divergência bloqueia a criação da PR.

### Contrato estrutural

`.github/workflows/pr-readiness-guard.yml` valida continuamente que os dois caminhos acima mantêm os controles fail-closed e executa `tests/test_auto_open_agent_pr.py` quando o contrato é alterado.

## Verificações v3

O script `scripts/pre_pr_readiness.py` seleciona verificações pelo diff contra `origin/main`:

- vínculo da execução ao HEAD SHA;
- branch não pode estar atrás da base;
- compilação dos arquivos Python alterados;
- `ruff check` obrigatório em todos os arquivos Python alterados;
- `bash -n` obrigatório em scripts shell alterados;
- parse de JSON alterado;
- parse e estrutura mínima de YAML alterado, incluindo workflows;
- execução de testes alterados e testes correspondentes a scripts quando localizados;
- descoberta de testes contratuais agregados que referenciem path, nome ou stem dos arquivos alterados;
- para perfil operacional, reutilização da suíte rápida já usada pelo `Fast CI - Operational Guardrails`;
- para frontend, `npm ci` e `npm run build`;
- para backend, sintaxe e testes diretamente relacionados são antecipados; a suíte integrada continua no CI da PR nesta versão.

## Controles contra falso positivo

O workflow executa:

- testes do contrato do próprio gate;
- um controle negativo deliberado com JSON inválido, que precisa ser detectado como falha;
- validação real do diff atual;
- artifact `pre-pr-readiness-<HEAD_SHA>` contendo `base_sha`, `head_sha`, `correlation_id`, checks, bloqueios e alertas.

O enforcement v2 acrescenta controles negativos para:

- ausência de run do Pre-PR Readiness no HEAD atual;
- run concluído sem sucesso;
- avanço da `main` após a evidência;
- tentativa de criação automática sem evidência válida.

Uma execução verde de commit anterior não é evidência válida para um novo HEAD.

## Enforcement v3 — prevenção de falso verde estático

A partir do v3, erros determinísticos de lint/sintaxe não podem ser postergados para o CI da PR. O mesmo HEAD precisa passar `py_compile`, Ruff e `bash -n` quando aplicável, além dos testes contratuais encontrados por referência. A fila governada exige a execução verde do `Pre-PR Readiness Gate`, impedindo merge de uma PR aberta por caminho que tenha contornado o criador governado.

## Limite explícito

O gate reduz falhas determinísticas antes da PR, mas não garante ausência absoluta de falhas posteriores. Checks dependentes de ambientes externos, credenciais, disponibilidade de serviços, E2E real, políticas de revisão ou concorrência continuam no ciclo normal da PR.

`READY_FOR_PR=passed` autoriza somente a abertura da PR. Não autoriza merge, deploy ou promoção de ambiente.

## Critério de conclusão do enforcement v2

- os dois caminhos canônicos de abertura de PR falham fechado sem `READY_FOR_PR=passed` do HEAD atual;
- testes positivos e negativos do autoabridor passam;
- o contrato estrutural confirma os controles nos scripts atuais;
- o `Pre-PR Readiness Gate` do próprio incremento fica verde no HEAD final;
- a PR do incremento só é criada depois dessa evidência;
- os checks completos da PR são revalidados no mesmo SHA;
- nenhum merge automático é executado por este incremento.
