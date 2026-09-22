# Merge Queue Governada

## Objetivo

Implementar uma fila de merge governada para aumentar o número de PRs paralelos sem elevar o risco de conflito, regressão ou quebra silenciosa após merge.

Fluxo operacional:

```text
PR → validação isolada
   → integração temporária contra main
   → smoke runtime
   → gate de elegibilidade
   → merge queue / auto-merge governado
```

## Escopo implementado

O workflow `.github/workflows/governed-merge-queue.yml` adiciona três estágios objetivos:

| Estágio | Finalidade | Bloqueia merge quando falha |
|---|---|---:|
| Validação isolada | Executa guardrails, smoke Python e checks frontend quando aplicável | Sim |
| Integração temporária | Simula merge contra `main` em branch efêmera local do runner | Sim |
| Smoke runtime | Executa `runtime_health_validator.py` em modo `report_only` e publica evidência | Sim |

## Decisão governada

Um PR só é considerado elegível para a fila quando:

1. a validação isolada termina com sucesso;
2. a integração temporária contra `main` não apresenta conflito;
3. o smoke runtime gera evidência sem erro;
4. demais workflows obrigatórios do repositório continuam verdes;
5. não há mudança crítica não governada em contratos, secrets, branch protection ou bootstrap global.

## Auto-merge

**Estado operacional atualizado:** o repositório deve manter `allow_auto_merge=true` para permitir o auto-merge nativo do GitHub em PRs abertos que já passaram pelos gates obrigatórios.

Com `allow_auto_merge=true`:

- o gate continua validando isolamento, integração temporária e smoke runtime;
- PRs elegíveis podem receber habilitação de auto-merge por PR;
- o merge efetivo só acontece após os checks obrigatórios ficarem verdes;
- o fluxo reduz intervenção manual sem remover governança.

Se `allow_auto_merge=false` voltar a aparecer na API do GitHub:

- o gate continua funcionando;
- o PR deve ser tratado por merge manual ou automação governada explícita;
- a pendência deve ser registrada como gap operacional de configuração do repositório.

## Política de paralelismo seguro

### Permitido com baixo risco

- observabilidade;
- dashboards e analytics;
- documentação viva;
- testes;
- runbooks;
- evidências operacionais;
- validações CI desacopladas.

### Controlado

- workflows principais;
- runtime bootstrap;
- dependências globais;
- shared contracts;
- autenticação/autorização;
- schema/openapi.

## Evidências

O workflow publica o artefato:

```text
artifacts/governed-merge-queue/
├── policy.json
├── runtime-health-validator.json
└── summary.md
```

### Campos decisórios de `policy.json`

| Campo | Significado |
|---|---|
| `eligible` | PR passou validação isolada + integração temporária |
| `allow_auto_merge` | Estado atual do repositório no GitHub |
| `native_auto_merge_available` | Espelho de `allow_auto_merge` para automação futura |
| `merge_path` | Caminho operacional recomendado (`native_auto_merge` ou `governed_pr_automation`) |

Essas evidências devem ser usadas no status executivo para diferenciar:

- estado declarado;
- estado validado;
- estado evidenciado;
- estado consolidado.

## Labels automáticas

| Label | Quando aplicar | Quando remover |
|---|---|---|
| `merge-queue:eligible` | Gate `merge-queue-gate` com sucesso | Qualquer falha nos estágios anteriores |

A label **não** autoriza merge sozinha. Ela sinaliza elegibilidade técnica da fila governada; o merge continua exigindo CI obrigatório e política de merge aprovada.

## Próximo incremento recomendado

Após estabilização do auto-merge nativo:

1. auditoria de branch protection acoplada ao resultado de `policy.json`;
2. relatório executivo de PRs paralelos elegíveis;
3. dashboard operacional de capacidade segura por domínio;
4. classificação automática de risco de conflito por arquivos alterados.


## Sincronização federada de branches

O workflow `.github/workflows/repository-governance-agent.yml` complementa a fila sem criar uma segunda rota de integração na `main`.

Quando a `main` avança:

1. lista PRs abertas com base `main`;
2. ignora draft, forks externos, conflitos e mergeabilidade desconhecida;
3. relê HEAD e base e seleciona somente PRs com `behind_by > 0`;
4. confirma novamente os mesmos SHAs no Git remoto antes da escrita;
5. em um repositório Git `bare`, calcula o merge por `merge-tree --write-tree` e cria o commit por `commit-tree`, sem checkout nem execução de código da branch candidata;
6. publica o commit exclusivamente na branch head por push **não-forçado** autenticado com a GitHub App;
7. relê o PR e exige que o novo HEAD contenha o SHA de base capturado com `behind_by=0`;
8. limita a três atualizações por execução para conter o fan-out de CI.

### Permissões

A leitura usa o `GITHUB_TOKEN` nativo somente com:

- `contents: read`;
- `pull-requests: read`.

A mutação usa token temporário da GitHub App `REQSYS_STACK_REBASE` com somente:

- `contents: write`.

O agente **não solicita mais `pull-requests: write`**. Essa permissão era exigida pelo endpoint REST `update-branch`; a sincronização atual escreve a branch diretamente pelo Git, preservando a identidade da App para que o novo SHA continue disparando os workflows normais do PR.

### Concorrência e fail-closed

O push não usa `--force`. Se a branch avançar depois da leitura, o push não pode sobrescrever o trabalho concorrente. O agente relê o PR:

- HEAD mudou => classifica como `stale_noop`;
- HEAD não mudou e o push falhou => `git_push_failed`, com job vermelho;
- `merge-tree` detecta conflito => `git_merge_tree_conflict`, sem escrita;
- push aceito sem comprovação pós-ação => falha o job.

A sincronização só atualiza a branch head. Ela **não integra o Pull Request na `main`**, não executa deploy e não altera branch protection, segredo ou permissão administrativa. A `Governed Merge Queue` / `Governed PR Automation` continuam sendo as únicas rotas de integração depois que os gates do novo HEAD forem revalidados.
