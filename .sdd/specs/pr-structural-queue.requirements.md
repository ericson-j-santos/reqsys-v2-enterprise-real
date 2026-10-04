# PR Structural Queue no PR CI Watch

## Objetivo

Fazer o GitHub reagir imediatamente ao avanço da `main` e avaliar a fila por estado estrutural antes de considerar somente CI.

## Prioridade

1. PR conflitante/inmergeável;
2. PR com `changed_files=0`, que pode indicar trabalho perdido;
3. PR atrás da `main`;
4. checks de CI.

Dentro da mesma classe, o PR mais antigo vem primeiro.

## Regras

- O mecanismo reutiliza `PR CI Watch`; não cria workflow paralelo.
- Um push na `main` dispara a avaliação estrutural.
- Conflitos e diff vazio são fail-closed e exigem reconciliação objetiva.
- Branch atrasada pode ser atualizada pelo endpoint oficial `update-branch` somente com `expected_head_sha`.
- No máximo uma branch é sincronizada por ciclo, evitando tempestade de CI.
- Nenhum force-push, fechamento/recriação de PR ou merge direto é realizado por esta fila estrutural.
- CI continua sendo avaliado depois que o estado estrutural estiver saudável.
- O sweep horário permanece apenas como rede de segurança.

## Critérios de aceite

- classificação estrutural coberta por testes;
- conflito precede empty-change e behind;
- unknown mergeability falha fechado;
- push em `main` aciona o job estrutural;
- atualização de branch usa SHA esperado;
- artifacts JSON/Markdown registram a decisão.

## Controle de fan-out

- `workflow_run` destinado a PR não deve criar execução quando o workflow de origem estiver na `main`.
- O `PR Evidence Gate` usa o CI principal como único sinal canônico de conclusão; os demais estados são lidos pelo HEAD atual.
- `PR CI Watch` e `Ollama CI Triage` excluem `main` no próprio gatilho, não apenas dentro do job.
- `Ollama CI Triage` mantém no máximo um diagnóstico útil por HEAD.
- `CI Observability` usa `concurrency` por workflow de origem + HEAD e `cancel-in-progress: true`.
- Workflows alterados devem usar referências externas de Actions fixadas por SHA.
- A correção deve reduzir criação de runs inúteis sem relaxar nenhum gate obrigatório do PR.
