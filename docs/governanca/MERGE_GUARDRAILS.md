# Merge Guardrails — ReqSys

## Objetivo

Impedir integração acidental ou prematura na `main`, preservando evidência atual, mergeabilidade e proteção contra mudança concorrente do HEAD.

O PR #58 nasceu após um incidente de merge prematuro em 2026-06-20. Desde então, o repositório evoluiu e hoje possui controles mais fortes do que o workflow isolado originalmente proposto. Este documento consolida a decisão no estado canônico atual, sem criar uma superfície de CI duplicada.

## Regra canônica atual

Um PR só pode ser integrado quando, no HEAD atual:

- estiver aberto e fora de draft;
- estiver com `behind_by=0`;
- estiver mergeável e sem conflitos;
- todos os workflows obrigatórios aplicáveis estiverem verdes;
- revisões/conversas exigidas estiverem satisfeitas;
- a evidência pertencer ao SHA vigente;
- a decisão de merge for invalidada se o HEAD mudar;
- a mutação de merge usar proteção equivalente a `expected_head_sha`.

A autorização operacional vigente permite merge automático quando todos esses critérios estiverem satisfeitos. Não é necessária uma confirmação manual adicional por PR quando a autorização já existe; a automação não pode, porém, contornar nenhum gate.

## Controles canônicos

### Pre-PR Readiness

`Pre-PR Readiness Gate` antecipa falhas determinísticas, exige branch atualizada e produz evidência vinculada ao HEAD avaliado.

### Governed Merge Queue

`Governed Merge Queue` revalida o contexto do PR, a estabilidade do SHA, os workflows obrigatórios e a integração contra a base real antes de considerar o PR elegível.

### Proteção contra corrida de HEAD

O fluxo de merge deve:

1. capturar o SHA avaliado;
2. validar checks e mergeabilidade nesse SHA;
3. reler o PR imediatamente antes da mutação;
4. abortar se o SHA mudou;
5. enviar o SHA esperado na chamada de merge.

### Branch protection / ruleset

A `main` deve continuar protegida contra force-push e exclusão e exigir os checks definidos pela governança vigente. Conversas bloqueantes devem ser resolvidas quando a proteção exigir.

## Checklist do PR

O template canônico contém a seção **Integração governada**, com verificação de:

- saída intencional de draft;
- `behind_by=0`;
- checks obrigatórios verdes;
- ausência de conflitos/conversas bloqueantes;
- evidência no SHA atual;
- rota governada de merge;
- validação pós-merge quando aplicável.

## Por que o workflow antigo não é restaurado

O arquivo histórico `.github/workflows/merge-guardrails.yml` fazia validações de checklist e estado do PR, mas hoje seria redundante com os controles canônicos acima e aumentaria a superfície de workflows.

Além disso, a versão histórica usava referência mutável de action e exigia confirmação final manual, ambos incompatíveis com a governança vigente. A correção preserva o objetivo do PR #58 sem reintroduzir mecanismos superados.

## Estados proibidos para merge

É proibido mergear quando qualquer uma destas condições ocorrer:

- PR em draft;
- branch atrás da `main`;
- conflito de merge;
- workflow obrigatório ausente, pendente, falho ou cancelado;
- HEAD diferente do SHA que foi validado;
- evidência reaproveitada de SHA anterior;
- revisão/conversa obrigatória pendente;
- tentativa de bypass de proteção.

## Pós-merge

Quando aplicável, validar a `main` resultante e registrar evidência no SHA efetivamente integrado. Falha pós-merge deve gerar correção nova e rastreável, sem reescrever histórico protegido.

## Decisão

O objetivo do PR #58 permanece válido: evitar merge prematuro. A implementação canônica é consolidar o checklist no template e reutilizar os mecanismos vigentes de Pre-PR Readiness, Governed Merge Queue, branch protection e proteção por SHA esperado, em vez de adicionar um workflow paralelo.
