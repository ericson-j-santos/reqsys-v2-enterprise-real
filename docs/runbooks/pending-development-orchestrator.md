# Pending Development Orchestrator

## Objetivo

Continuar automaticamente trabalhos pendentes do ReqSys sem criar um segundo pipeline de entrega. O orquestrador reutiliza os gates e executores existentes e só encaminha itens explicitamente elegíveis.

## Fontes de trabalho

1. Issues contendo o marcador `<!-- pending-development-orchestrator:auto -->`.
2. Issues com label `orchestrator:auto`.
3. Issues `[AUTO-NEXT]` criadas pelo `Autonomous Delivery Cycle` após merge governado bem-sucedido.
4. Pull Requests cujo branch começa com `copilot/`.
5. Pull Requests explicitamente marcadas com `orchestrator:auto-fix`.

Issues e PRs fora dessas condições não são alteradas automaticamente.

## Roteamento

| Situação | Executor | Regra |
|---|---|---|
| Falha transitória de CI | `Actions Auto Operator` | Reexecuta apenas falhas allowlisted/transitórias. |
| Desenvolvimento em issue | GitHub Copilot coding agent | Atribuição da issue ao agente, branch isolada e PR posterior. |
| CI determinístico em PR elegível | GitHub Copilot coding agent | Comentário `@copilot` solicita correção da causa raiz no mesmo PR. |
| Produção, segredos, permissões administrativas, branch protection, ação destrutiva ou merge automático | Gate humano | Nenhuma execução automática. |
| Agent Increment Gate bloqueado | Gate operacional | Nenhuma execução automática. |

O orquestrador não faz merge, não faz deploy de produção, não altera segredos, permissões administrativas ou branch protection.

## Pré-requisito para o Copilot coding agent

A automação de desenvolvimento requer o secret de repositório `COPILOT_AGENT_TOKEN`.

O valor deve ser um token de usuário compatível com a API do GitHub Copilot coding agent e com acesso mínimo necessário ao repositório. Nunca registrar o valor em arquivo, log, issue, artifact ou documentação.

Sem esse secret:

- auditoria continua funcionando;
- rotas de CI que usam `GITHUB_TOKEN` continuam disponíveis;
- rotas que precisam do Copilot ficam `blocked` com `missing_copilot_agent_token`;
- a execução agendada falha fechada quando existir trabalho elegível que dependa do token.

## Modos

### Audit

```bash
python scripts/pending_development_orchestrator.py \
  --repo owner/repo \
  --base-branch main \
  --mode audit \
  --status-json artifacts/coordenador-status/coordenador-status.json
```

Classifica e planeja sem atribuir agente, comentar PR ou disparar rerun.

### Execute

```bash
GITHUB_TOKEN=*** COPILOT_AGENT_TOKEN=*** \
python scripts/pending_development_orchestrator.py \
  --repo owner/repo \
  --base-branch main \
  --mode execute \
  --status-json artifacts/coordenador-status/coordenador-status.json
```

O workflow `.github/workflows/pending-development-orchestrator.yml` executa em `execute` quando disparado pelo agendamento horário. O disparo manual começa em `audit` por segurança.

## Idempotência e concorrência

- Issue já atribuída a `copilot-swe-agent[bot]` não é atribuída novamente.
- O `Actions Auto Operator` é disparado no máximo uma vez por execução do orquestrador.
- Correção de PR grava marcador com o `HEAD SHA`; o mesmo SHA não recebe a mesma solicitação duas vezes.
- Após duas tentativas de correção por Copilot no mesmo PR, o item é escalado para gate humano.
- O workflow usa `concurrency` para impedir ciclos concorrentes sobre a mesma branch base.

## Integração com Autonomous Delivery Cycle

Após um merge governado, o `Autonomous Delivery Cycle` extrai os próximos incrementos declarados no corpo do PR e cria uma Issue `[AUTO-NEXT]` para cada um. A issue recebe o marcador automático consumido por este orquestrador.

O handoff só acontece após merge bem-sucedido. Em `dry_run`, o próximo incremento permanece apenas como evidência capturada.

## Evidência

Artifact: `pending-development-orchestrator-evidence`.

Arquivos principais:

- `pending-development-orchestrator.json`;
- `summary.md`;
- `stdout.json`;
- `coordenador-status.json` usado pela mesma execução.

Cada execução registra `correlation_id`, modo, rota, status, motivo, tipo de incremento e se houve ação real.

## Validação mínima

```bash
python -m pytest tests/test_pending_development_orchestrator.py -q
```

O teste cobre seleção explícita, gate de risco, integração com Agent Increment Gate, idempotência, CI transitório, CI determinístico no mesmo PR, ausência do token e handoff do ciclo autônomo.

## Critério de conclusão operacional

O incremento está funcionalmente validado apenas quando:

1. o `Pre-PR Readiness Gate` estiver verde no HEAD atual;
2. os checks da PR estiverem verdes no mesmo SHA;
3. um run do orquestrador em `audit` produzir classificação correta;
4. quando `COPILOT_AGENT_TOKEN` estiver provisionado, um caso positivo real criar/continuar uma sessão do Copilot;
5. um caso de risco alto permanecer bloqueado sem efeito externo;
6. uma repetição da mesma entrada não duplicar atribuição/comentário.

Enquanto o token do Copilot não estiver provisionado e um caso real não for observado, classificar o estado como `parcialmente validado`.
