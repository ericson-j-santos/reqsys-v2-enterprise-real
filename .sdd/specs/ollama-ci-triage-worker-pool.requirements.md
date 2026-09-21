# Requisitos — Ollama CI Triage no Worker Pool

## Escopo

Usar Ollama no PC24x7 como primeiro nível automático de análise de falhas de CI em Pull Requests do ReqSys e escalar somente falhas técnicas elegíveis ao Codex Worker Pool existente.

## Requisitos funcionais

1. Gatilho automático orientado por `workflow_run` concluído, restrito a workflows CI conhecidos e sem agendamento.
2. Execução no runner PC24x7 allowlisted; Ollama e Worker Pool somente por loopback.
3. Caminho automático faz checkout da branch padrão confiável, nunca do código do PR que originou o evento.
4. Logs são entrada não confiável: sanitizar, limitar e enviar ao Ollama sem ferramentas.
5. Ollama responde JSON estruturado com categoria, confiança, causa, ação e evidências.
6. Somente `code`, `test`, `config` e `dependency` com confiança >= 0.75 podem ser elegíveis ao escalonamento.
7. `security`, `governance`, `transient` e `unknown` nunca são autoescaladas.
8. A política determinística, e não o modelo, decide o escalonamento; o modelo sozinho nunca basta para autorizar correção.
9. O escalonamento exige também um padrão determinístico técnico conhecido e é bloqueado por sinais de permissão, conflito, quota, artifact ou timeout.
10. PR deve estar aberto, no mesmo repositório e no mesmo SHA analisado; fork externo ou SHA obsoleto falha fechado.
11. Worker Pool recebe `target_branch` opcional; quando presente, preserva a branch existente do PR. `main`, `master` e `develop` são proibidas.
12. Chamadas legadas sem `target_branch` preservam a geração atual de branch.
13. Request ID do CI é idempotente por repositório, PR e SHA.
14. Enqueue comprova replay `created=false`, mesmo `task_id` e leitura independente com branch/SHA corretos.
15. Em modo `execute`, comentário sanitizado é publicado uma vez por run; logs brutos não são reproduzidos.
16. Nenhum caminho deste incremento executa merge, deploy, promoção, segredo, bypass de gate ou administração.
17. O workflow oferece `dry_run` manual para validar Ollama e evidência antes da ativação automática na `main`.

## Critérios de aceite

- testes unitários cobrem política positiva e controles negativos;
- bloqueios de fork externo, SHA obsoleto, branch protegida e baixa confiança são comprovados;
- Worker Pool comprova `target_branch` retrocompatível e replay idempotente;
- contrato do workflow comprova checkout seguro, permissões mínimas, allowlist e ausência de loop;
- Pre-PR Readiness retorna `READY_FOR_PR=passed` no HEAD exato e `behind_by=0`;
- `dry_run` real no PC24x7 produz JSON estruturado do Ollama vinculado a run real sem comentar/enfileirar;
- integração externa permanece parcial até `execute` real enfileirar a branch do mesmo PR e leitura independente confirmar a task.

## Fora de escopo

- merge automático;
- deploy/restart do Worker Pool;
- correção direta pelo Ollama;
- HML/STG/PROD;
- exposição pública do Ollama ou Worker Pool.
