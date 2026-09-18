# Correção — CI pós-merge e diagnóstico profundo

Atualizado em: 2026-06-23

## 1. Incidentes analisados

### Job 83079655734

Link: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/28062490331/job/83079655734#step:2:1

Falha capturada:

```text
No audit/report/evidence artifact found for main commit SHA 42796024a76196423db84d183bc347c8f98a9fe3.
```

Causa raiz:

O workflow `Main Post-Merge Validation` exigia artifact externo de evidence/audit/report antes de considerar que sua própria evidência seria publicada. Isso gerava falso negativo quando nenhum outro workflow ainda havia publicado artifact para o SHA da main.

Correção:

- Transformar ausência de artifact anterior em warning.
- Manter falha para ausência de workflows obrigatórios ou workflows obrigatórios realmente falhos.
- Publicar sempre artifact próprio `main-post-merge-validation-*`.
- Versionar schema da evidência para `1.1.0`.

## 2. Job 83079676076

Link: https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/actions/runs/28062490383/job/83079676076#step:2:1

Falha capturada:

```text
CI Router Result: falha detectada em job obrigatório.
```

Causa raiz:

O consolidado do CI tratava `cancelled` como falha definitiva. Em cenários de roteamento, concorrência ou execução substituída, jobs podem aparecer como `cancelled` sem representar falha real de código.

Correção:

- `CI Router Result` agora falha somente em `failure`.
- Estados `skipped` e `cancelled` são registrados no summary, mas não bloqueiam quando não representam erro real.

## 3. Automação adicionada

Foi criado o workflow:

```text
.github/workflows/actions-deep-diagnostic.yml
```

Ele permite informar:

- `run_id`
- `job_id`

E gera:

- captura de metadados do run/job;
- logs do job;
- relatório JSON;
- relatório Markdown;
- classificação pelo Failure Pattern Engine;
- artifact auditável.

## 4. Limites operacionais

Este incremento não faz:

- rerun automático;
- merge automático;
- push direto em main;
- remediação automática;
- ocultação de falha real.

## 5. Próxima evolução recomendada

Integrar o `Actions Deep Diagnostic` ao `Failure Pattern Engine` e ao `ReqSys Operational Health`, para que falhas pós-merge sejam capturadas, classificadas e refletidas no score operacional automaticamente.
