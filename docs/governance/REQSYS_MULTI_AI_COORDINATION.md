# REQSYS#001 — Coordenação Multi-IA e Governança Global

## Estado canônico

- Frente: `REQSYS#001`
- Papel: IA Coordenadora
- Modo: governado, incremental e fail-closed
- Branch ativa deste incremento: `agent/reqsys-001-governance-reconciliation-v1`
- Branch base: `main`
- Produção acessada por este incremento: `false`

Este documento é o contrato canônico para coordenação das frentes especializadas do ReqSys v2 Enterprise. Ele substitui a dependência de branches históricas como fonte de verdade operacional.

## Responsabilidades da Coordenadora

1. Revalidar repositório, PR, checks, conflitos e evidências antes de decidir.
2. Priorizar o menor incremento correto e rastreável.
3. Bloquear merge quando CI, escopo, segurança, evidência ou Definition of Done estiverem incompletos.
4. Impedir promoção de conformidade ou produção baseada apenas em declaração textual.
5. Integrar entregas das frentes sem executar features grandes diretamente.
6. Registrar estado evidenciado, estado alvo, riscos, bloqueios e próximo incremento.

## Frentes e ownership

| Frente | Ownership principal | Branch nova quando necessária |
|---|---|---|
| REQSYS#001 Coordenadora | integração, prioridade, risco, merge e DoD | `agent/reqsys-001-*` |
| REQSYS#002 Runtime | deploy, saúde pública, rollout e rollback | `agent/reqsys-002-*` |
| REQSYS#003 Observabilidade | logs, métricas, traces e analytics | `agent/reqsys-003-*` |
| REQSYS#004 UX/UI | operação navegável e evidência visual | `agent/reqsys-004-*` |
| REQSYS#005 Governança CI | workflows, gates, branch protection e drift | `agent/reqsys-005-*` |
| REQSYS#006 Autônoma | diagnóstico e remediação governada | `agent/reqsys-006-*` |
| REQSYS#007 Docs Vivas | ADRs, diagramas, changelog e architecture graph | `agent/reqsys-007-*` |

## Reconciliação das branches históricas

Validação realizada em 31/07/2026 contra a `main` do repositório.

| Branch histórica | Estado | Divergência evidenciada | Decisão |
|---|---|---:|---|
| `ai/runtime-public` | `superseded` | 1 commit à frente e 818 atrás | não fazer merge ou rebase; extrair somente mudanças ainda úteis para branch nova |
| `ai/observability` | `superseded` | 11 commits à frente e 818 atrás | não fazer merge ou rebase; revisar arquivos individualmente e reaplicar sobre a `main` |
| `ai/ux-operacional` | `superseded` | 5 commits à frente e 818 atrás | não fazer merge ou rebase; reaplicar somente incremento validado e sem conflito |
| `ai/coordinator-governance` | `not_created` | não aplicável | substituída pelo padrão `agent/reqsys-001-*` |
| `ai/governance-initial` | `not_created` | não aplicável | criar somente a partir da `main` atual quando houver escopo autorizado |
| `ai/autonomous-remediation-initial` | `not_created` | não aplicável | criar somente após estabilização das dependências |
| `ai/living-architecture-initial` | `not_created` | não aplicável | criar somente com contrato de entrega definido |

### Regra de salvamento de trabalho antigo

1. Criar branch nova a partir da `main` atual.
2. Inspecionar o diff histórico por arquivo.
3. Reaplicar manualmente ou por cherry-pick apenas commits isolados sem dependências obsoletas.
4. Executar testes do domínio e os checks governados.
5. Registrar no PR a branch histórica de origem e o que foi descartado.

É proibido usar merge amplo ou rebase de centenas de commits apenas para recuperar uma alteração pequena.

## Política de PR

- Ideal: 1 a 8 arquivos alterados.
- Aceitável: 9 a 20 arquivos com justificativa.
- Acima de 20 arquivos: dividir, salvo migração indivisível com evidência.
- Um domínio principal por PR.
- Branch sempre criada da `main` atual.
- PR inicialmente em draft quando ainda houver validação pendente.
- Nenhum merge com checks obrigatórios pendentes, falhos ou ausentes.
- `production_touched` deve ser declarado explicitamente.

## Definition of Done global

Um incremento está pronto somente quando:

- escopo e risco estão descritos;
- branch não está desatualizada de forma material;
- CI obrigatório está verde no SHA atual;
- não há conflito ou review thread bloqueante;
- testes do domínio foram executados;
- documentação e changelog foram avaliados;
- artifacts/evidências estão publicados quando aplicável;
- rollback está definido;
- segredos e dados pessoais não foram expostos;
- produção não foi promovida por inferência ou declaração não verificável.

## Gates de bloqueio

Bloquear merge ou produção quando ocorrer qualquer um dos seguintes estados:

- autenticação desabilitada em produção;
- CORS irrestrito em produção;
- JWT sem validação de emissor e audiência;
- segredo, token, conexão ou PII em log, commit ou artifact;
- auditoria sem `correlation_id` quando exigido;
- deploy sem rollback conhecido;
- controle BACEN crítico em `partial` ou `gap` quando o fluxo exigir conformidade integral;
- aprovação humana registrada, mas ainda não canonicalizada nos arquivos formais;
- workflow produtivo acessando environment ou secret antes do gate correspondente.

## Contrato de status das frentes

Cada frente deve reportar:

```text
REQSYS#00X • NOME_DA_FRENTE

Implementado:
Validado:
Evidenciado:
Pendente:
Bloqueios:
Riscos:
Branch/PR:
CI:
Produção tocada:
Próximo passo recomendado:
```

A Coordenadora responde com uma decisão única:

- `PROSSEGUIR`
- `CORRIGIR`
- `AGUARDAR_CI`
- `DIVIDIR_PR`
- `SUBSTITUIR_BRANCH_OBSOLETA`
- `BLOQUEADO`
- `PRONTO_PARA_MERGE`

## Reconciliação da PR #1127

A PR histórica `#1127` está divergente da `main` e não deve ser atualizada por rebase amplo. A intenção documental será preservada da seguinte forma:

- estruturas `runtime/`, `services/`, `ops-dashboard/`, `ia-ml-lab/` e governança já existentes na `main` permanecem como fonte atual;
- comandos e workflows devem ser documentados somente após conferência contra os arquivos executáveis atuais;
- este contrato concentra a governança multi-IA que faltava;
- a PR histórica deve ser encerrada como substituída pelo incremento REQSYS#001 atual, sem merge do branch obsoleto.

## Próximo incremento após esta reconciliação

1. Obter os campos formais ainda ausentes para BACEN-01 e BACEN-08.
2. Atualizar os arquivos canônicos, executar os geradores de evidência e somente então avaliar promoção para `implemented`.
3. Revalidar a readiness das políticas Teams no runtime.
4. Reconciliar backlog antigo com evidência atual, sem fechar demandas apenas por implementação técnica.
