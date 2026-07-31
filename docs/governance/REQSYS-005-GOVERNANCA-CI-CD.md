# REQSYS#005 — Governança CI/CD e Gates

## Identificação

| Campo | Valor |
|---|---|
| Frente | `REQSYS#005` |
| Domínio | Governança / CI/CD |
| Capacidade | `GOVERNANCA_CI • GATES_WORKFLOWS` |
| Data de reconciliação | 31/07/2026 14:56 BRT |
| Estado evidenciado | 96% |
| Estado alvo | 100% Padrão Ouro Consolidado |
| Situação | Operacionalmente verde; consolidação pós-merge pendente |

## Missão

Garantir que alterações do ReqSys sejam integradas com CI determinístico, gates de segurança e governança, artifacts íntegros, política de merge segura, rastreabilidade e ausência de bypass silencioso.

## Estado evidenciado

- A `main` estava no commit `56e25dd35343d21b4fdc1774087de44cd4c45f97` no momento desta reconciliação.
- O PR [#1139](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/pull/1139) foi mergeado e corrigiu o deadlock da fila `Padrão Ouro Delivery`.
- Os gates principais do SHA do PR concluíram com sucesso, incluindo CI Enterprise, Governança, PR Evidence, Merge Readiness, Branch Protection, Security Baseline, Conflict Guard e Governed Merge Queue.
- Artifacts de evidence, merge readiness, branch protection e security baseline foram publicados com digest SHA-256.
- Não havia PR aberto no repositório no momento da captura anterior ao início deste incremento.
- A branch permanente `ai/governance-ci` não existe e deixa de ser requisito operacional.

## Estratégia oficial de branches efêmeras

A frente REQSYS#005 passa a usar branches curtas, criadas a partir da `main` atual e descartadas após o merge. Não deve existir branch permanente de integração específica da frente.

### Convenção

| Tipo de incremento | Prefixo recomendado | Exemplo |
|---|---|---|
| Consolidação documental ou governança | `agent/` | `agent/reqsys-005-governance-reconciliation` |
| Correção de causa raiz | `fix/` | `fix/padrao-ouro-delivery-queue-deadlock` |
| Correção crítica e isolada | `hotfix/` | `hotfix/required-check-contract` |

### Guard rails obrigatórios

1. Criar a branch a partir do SHA atual da `main`.
2. Manter um único objetivo técnico por PR.
3. Preferir de 1 a 8 arquivos modificados; alterações acima de 20 arquivos exigem justificativa explícita.
4. Abrir PR em draft e mantê-lo assim até os gates obrigatórios ficarem verdes.
5. Não executar push direto na `main`.
6. Não usar `force push` para reconciliar histórico.
7. Não relaxar gate, branch protection, segurança ou evidência para obter resultado verde.
8. Registrar risco, rollback, impacto em produção e evidências no corpo do PR.
9. Exigir merge readiness, conflict guard, CI, governance, security e evidence no SHA atual.
10. Excluir a branch efêmera após o merge, preservando PR, commits, runs e artifacts como trilha de auditoria.

## Definition of Done da frente

Um incremento REQSYS#005 somente está concluído quando:

- o PR possui escopo mínimo e rastreável;
- a branch está atualizada e sem conflito com a `main`;
- os checks obrigatórios estão verdes no mesmo `head_sha`;
- artifacts esperados existem, não estão expirados e possuem digest;
- permissões de workflows seguem privilégio mínimo;
- o rollback está documentado;
- o merge ocorre pela política governada;
- a validação pós-merge da `main` é registrada sem promover estado não evidenciado.

## Reconciliação do backlog

| Item | Decisão |
|---|---|
| Issue [#1001](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/1001) | Encerrar após registrar que os PRs #997 e #999 foram mergeados com CI e PR Evidence verdes; backlog genérico residual deve permanecer em #663. |
| Issue [#663](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/663) | Manter aberta e atualizar o checklist: CI, Evidence, E2E e Merge Readiness possuem evidências verdes; Fly drift, consolidação operacional e evidência pós-merge específica permanecem pendentes. |
| Branch `ai/governance-ci` | Não criar. Substituída formalmente pelo modelo de branches efêmeras. |

## Critério para declarar 100%

A frente permanece em **96%** até que todos os itens abaixo estejam evidenciados:

- este contrato esteja mergeado na `main` por PR governado;
- exista run pós-merge concluído com sucesso para a `main` em SHA que contenha este incremento;
- a evidência pós-merge registre URL do run, SHA, resultado, artifacts e digests aplicáveis;
- não exista required check crítico falho ou pendente para o SHA consolidado;
- as issues #663 e #1001 estejam reconciliadas com o estado real, sem checklist obsoleto;
- qualquer limitação remanescente esteja atribuída à frente responsável, sem inflar a maturidade de REQSYS#005.

## Decisão de maturidade

**100% Padrão Ouro Consolidado não está declarado neste documento.** A promoção para 100% depende de evidência pós-merge válida na `main`, não apenas do merge ou do CI do PR.
