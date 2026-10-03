# Product Intelligence Final Evidence Index

## Objetivo

Consolidar, em um índice final governado, as evidências mínimas para declarar a frente de Product Intelligence auditável, rastreável e pronta para decisão operacional.

Este documento não declara prontidão de produção por si só. Ele define o formato canônico de evidência, os critérios de aceite e as lacunas que devem permanecer visíveis até validação real em `main`.

## Escopo

O índice cobre evidências de:

- requisitos e rastreabilidade funcional;
- decisões arquiteturais e ADRs;
- artefatos de validação gerados por GitHub Actions;
- documentação operacional e runbooks;
- sinais de segurança, privacidade e governança;
- estado de UX, usuário final e produção.

## Fora do escopo

- deploy automático;
- alteração de secrets;
- bypass de branch protection;
- aprovação humana simulada;
- declaração automática de produção verde sem checks reais.

## Modelo de maturidade

| Dimensão | Critério mínimo | Evidência esperada |
|---|---|---|
| Técnico | Implementação versionada, validada e rastreável | PR, diff, checks e artifacts |
| Operacional | Runbook, owner lógico e plano de reversão | runbook e relatório operacional |
| Usuário final | Fluxo validável e critérios de aceite claros | roteiro de validação e evidência UX |
| Governança | ADR, riscos, gates e trilha de decisão | ADR, checklist e artifacts |
| Produção | Segurança, deploy e rollback avaliados | gates pós-merge e evidência de ambiente |

## Índice canônico de evidências

Cada evidência deve ser registrada com:

- `id` único e estável;
- `tipo` da evidência;
- `origem` verificável;
- `link` clicável quando disponível;
- `estado` explícito (`pending`, `validated`, `blocked`, `not_applicable`);
- `owner` lógico;
- `data_referencia` em ISO 8601;
- `risco_residual` objetivo;
- `proximo_passo` recomendado.

## Gates obrigatórios

1. Todos os checks bloqueantes do PR devem estar verdes.
2. O PR não pode estar em draft para merge.
3. `mergeable` deve estar positivo no momento da decisão.
4. Não pode haver review thread pendente ou requested changes ativo.
5. Artifacts críticos devem existir ou estar explicitamente marcados como `not_applicable` com justificativa.
6. Nenhum gate de segurança pode ser ignorado.
7. Validação pós-merge em `main` deve ser registrada antes de declarar consolidação.

## Evidências mínimas para Product Intelligence

| ID | Evidência | Estado inicial | Observação |
|---|---|---|---|
| PI-FEI-001 | PR do incremento | pending | Preenchido após abertura do PR |
| PI-FEI-002 | Checks do PR | pending | Capturado via GitHub Actions |
| PI-FEI-003 | Artifacts de evidência | pending | JSON/Markdown/summary quando workflow existir |
| PI-FEI-004 | ADR do índice final | validated | `docs/adr/ADR-033-product-intelligence-final-evidence-index.md` |
| PI-FEI-005 | Runbook operacional | validated | `docs/runbooks/product-intelligence-final-evidence-index.md` |
| PI-FEI-006 | Validação pós-merge na main | pending | Obrigatório após merge |

## Saída esperada

O estado final esperado é um índice que permita responder, sem inferência manual frágil:

- qual PR entregou cada parte da Product Intelligence;
- quais checks validaram a entrega;
- quais artifacts sustentam a decisão;
- quais riscos permanecem;
- se o fluxo está pronto para usuário final, homologação ou produção.

## Critério de aceite deste incremento

Este incremento é aceito quando:

- o documento canônico existir;
- schema e exemplo forem versionados;
- runbook e ADR estiverem vinculados;
- CI do PR estiver verde;
- o PR for mergeável sem conflito;
- a validação pós-merge for capturada em execução posterior.
