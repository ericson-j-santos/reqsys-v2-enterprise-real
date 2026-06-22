# Estratégia de Aceleração de CI — ReqSys

## Objetivo

Reduzir o tempo de espera em pull requests sem reduzir governança, rastreabilidade, segurança ou qualidade operacional.

## Decisão operacional

O fluxo de CI passa a ser organizado em camadas:

1. **Fast path obrigatório**: validações rápidas e determinísticas para PRs pequenos.
2. **Validações pesadas condicionais**: E2E, auditorias profundas e validações completas executadas somente quando o escopo justificar.
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

### Pós-merge

Em `main`, as validações completas podem rodar para preservar evidência de release sem bloquear PR pequeno.

## Ganho esperado

- PRs backend pequenos deixam de aguardar Playwright.
- PRs apenas de documentação deixam de executar suites desnecessárias.
- O tempo principal de feedback passa a depender do fast path.

## Regras de governança

- Nenhum job pesado deve ser removido sem substituição por execução condicional ou pós-merge.
- Jobs não aplicáveis devem ser `skipped`, não falhos.
- Falhas reais continuam bloqueando merge.
- Evidências devem permanecer publicadas como artifact ou job summary.

## Próximos incrementos recomendados

1. separar `ci-security.yml` para auditorias profundas;
2. separar `ci-e2e.yml` com `workflow_dispatch`, pós-merge e label `e2e`;
3. ativar testes afetados no backend;
4. habilitar merge queue quando a proteção de branch permitir;
5. criar dashboard de métricas de duração de CI.
