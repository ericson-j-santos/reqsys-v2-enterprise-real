# Estratégia de Aceleração de CI — ReqSys

## Objetivo

Reduzir o tempo de espera em pull requests sem reduzir governança, rastreabilidade, segurança ou qualidade operacional.

## Decisão operacional

O fluxo de CI passa a ser organizado em camadas:

1. **Fast path obrigatório**: validações rápidas e determinísticas para PRs pequenos.
2. **Validações pesadas condicionais**: E2E, auditorias profundas, revisão IA/CodeRabbit e validações completas executadas somente quando o escopo justificar.
3. **Pós-merge governado**: validações completas continuam existindo em `main`, release e execuções manuais.

## Política de execução

### Sempre em PR

- roteamento por arquivos alterados;
- guardrails de governança;
- backend lint/test quando houver alteração em `backend/`;
- frontend build quando houver alteração em `frontend/`;
- validações de workflow quando houver alteração em `.github/workflows/`.

### Condicional em PR

E2E responsivo deve rodar apenas quando:

- o PR tiver label `e2e`;
- o PR tiver label `full-ci`;
- houver alteração em fluxo crítico de frontend;
- o evento for `workflow_dispatch`;
- a execução ocorrer em `main` após merge.

Revisão IA/CodeRabbit profunda deve ser tratada como condicional quando:

- o PR tiver label `deep-review`;
- o PR tiver label `full-ci`;
- houver alteração em segurança, autenticação, autorização, secrets, deploy ou produção;
- houver mudança arquitetural transversal;
- o PR exceder escopo recomendado de micro PR;
- a execução ocorrer em `main`, release ou nightly.

### Pós-merge

Em `main`, as validações completas podem rodar para preservar evidência de release sem bloquear PR pequeno.

## Guardrails para CodeRabbit e revisão IA

A política oficial para revisão IA está documentada em:

- `docs/adr/ADR-0021-coderabbit-fast-review-governance.md`;
- `docs/governance/CODERABBIT_FAST_REVIEW_GUARDRAILS.md`.

Diretrizes resumidas:

- preferir PRs pequenos e especializados;
- não usar CodeRabbit como substituto de testes determinísticos;
- não deixar arquivos gerados, HTML autocontido, coverage, dist, artifacts e lockfiles inflarem revisão quando não forem o alvo da mudança;
- separar CI Fast de Deep Review;
- usar labels como `fast-path`, `deep-review`, `full-ci`, `docs-only`, `workflow-only` e `security-critical`.

## Ganho esperado

- PRs backend pequenos deixam de aguardar Playwright.
- PRs apenas de documentação deixam de executar suites desnecessárias.
- PRs de workflow pequenos deixam de aguardar revisão profunda quando CI Fast é suficiente.
- O tempo principal de feedback passa a depender do fast path.
- CodeRabbit passa a agregar valor em mudanças relevantes sem bloquear todo incremento trivial.

## Regras de governança

- Nenhum job pesado deve ser removido sem substituição por execução condicional ou pós-merge.
- Jobs não aplicáveis devem ser `skipped`, não falhos.
- Falhas reais continuam bloqueando merge.
- Evidências devem permanecer publicadas como artifact ou job summary.
- Mudanças de segurança, auth, produção, secrets e dados sensíveis exigem revisão profunda.
- Revisão IA não substitui testes, SAST, validação de workflow, revisão humana ou gates de produção.

## Próximos incrementos recomendados

1. separar `ci-security.yml` para auditorias profundas;
2. separar `ci-e2e-governado.yml` com `workflow_dispatch`, pós-merge e label `e2e`;
3. ativar testes afetados no backend;
4. habilitar merge queue quando a proteção de branch permitir;
5. criar dashboard de métricas de duração de CI;
6. configurar, quando suportado, exclusões de arquivos gerados/artefatos para revisão IA/CodeRabbit;
7. automatizar labels `fast-path`, `workflow-only`, `docs-only`, `deep-review` e `security-critical` por paths alterados.
