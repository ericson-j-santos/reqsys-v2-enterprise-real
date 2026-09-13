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

## Verificações v1

O script `scripts/pre_pr_readiness.py` seleciona verificações pelo diff contra `origin/main`:

- vínculo da execução ao HEAD SHA;
- branch não pode estar atrás da base;
- compilação dos arquivos Python alterados;
- parse de JSON alterado;
- parse e estrutura mínima de YAML alterado, incluindo workflows;
- execução de testes alterados e testes correspondentes a scripts quando localizados;
- para perfil operacional, reutilização da suíte rápida já usada pelo `Fast CI - Operational Guardrails`;
- para frontend, `npm ci` e `npm run build`;
- para backend, sintaxe e testes diretamente relacionados são antecipados; a suíte integrada continua no CI da PR nesta versão.

## Controles contra falso positivo

O workflow executa:

- testes do contrato do próprio gate;
- um controle negativo deliberado com JSON inválido, que precisa ser detectado como falha;
- validação real do diff atual;
- artifact `pre-pr-readiness-<HEAD_SHA>` contendo `base_sha`, `head_sha`, `correlation_id`, checks, bloqueios e alertas.

Uma execução verde de commit anterior não é evidência válida para um novo HEAD.

## Limite explícito

O gate reduz falhas determinísticas antes da PR, mas não garante ausência absoluta de falhas posteriores. Checks dependentes de GitHub, ambientes externos, credenciais, disponibilidade de serviços, E2E real, políticas de revisão ou concorrência continuam no ciclo normal da PR.

## Critério de conclusão deste incremento

- workflow dispara por `push` antes de existir PR;
- testes do gate e controle negativo passam;
- execução real do HEAD termina `success`;
- artifact fica vinculado ao mesmo HEAD;
- somente depois disso a PR do próprio incremento pode ser criada.
