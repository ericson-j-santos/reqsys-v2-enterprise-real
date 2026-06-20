# Merge Guardrails — ReqSys

## Objetivo

Impedir merge acidental ou prematuro antes da conclusão dos gates mínimos de qualidade, governança e rastreabilidade.

Este documento formaliza a regra operacional: nenhum PR deve ser integrado na `main` antes de CI verde, revisão concluída, PR fora de draft e validação explícita pós-check.

---

## Incidente motivador

Em 2026-06-20, o PR #54 foi mergeado antes de aguardar a validação final da esteira. O evento expôs a necessidade de um guardrail explícito para evitar que decisões manuais avancem antes dos gates.

---

## Regra canônica

Um PR só pode ser mergeado quando todos os critérios abaixo estiverem satisfeitos:

| Gate | Obrigatório | Critério |
|---|---:|---|
| PR aberto | Sim | `state = open` |
| PR não draft | Sim | `draft = false` somente após CI verde |
| CI verde | Sim | Todos os checks obrigatórios com sucesso |
| Revisão concluída | Sim | Aprovação/revisão humana ou técnica registrada |
| Sem conflitos | Sim | Branch mergeável |
| Changelog/docs | Sim | Atualização aplicável ao escopo |
| Pós-validação planejada | Sim | Plano de validação pós-merge documentado |

---

## Estados proibidos para merge

É proibido executar merge quando:

- PR estiver em draft;
- CI estiver `queued`, `in_progress`, `pending`, `failed`, `cancelled` ou ausente;
- não houver revisão registrada;
- o PR estiver divergente sem atualização com `main`;
- houver alerta de segurança, segredo, token ou configuração sensível;
- a descrição não contiver checklist de release;
- houver CodeRabbit, review ou comentário bloqueante pendente;
- o ambiente alvo não estiver declarado.

---

## Checklist obrigatório no PR

Todo PR deve conter este bloco antes de ser marcado como pronto para revisão:

```markdown
## Merge Guardrails

- [ ] PR mantido em draft durante implementação.
- [ ] CI executado e verde.
- [ ] Revisão concluída.
- [ ] Sem comentários bloqueantes pendentes.
- [ ] Ambiente alvo declarado.
- [ ] Documentação/ADR/CHANGELOG atualizados quando aplicável.
- [ ] Plano de validação pós-merge documentado.
- [ ] Merge autorizado somente após confirmação final.
```

---

## Fluxo operacional obrigatório

1. Criar branch.
2. Abrir PR em draft.
3. Executar implementação.
4. Aguardar CI.
5. Corrigir falhas.
6. Validar novamente.
7. Atualizar documentação viva.
8. Marcar ready for review.
9. Revisar.
10. Realizar squash merge.
11. Validar pós-merge.
12. Atualizar monitoramento operacional.

---

## Medidas técnicas recomendadas

### Branch protection

Configurar no GitHub para `main`:

- Require pull request before merging.
- Require approvals.
- Require status checks to pass before merging.
- Require branches to be up to date before merging.
- Block force pushes.
- Block deletions.
- Require conversation resolution before merging.
- Restrict bypass quando possível.

### GitHub Actions guard

Criar workflow que falhe quando:

- PR estiver draft e alguém tentar promover indevidamente;
- corpo do PR não tiver checklist de guardrails;
- checks obrigatórios não forem encontrados;
- labels obrigatórias não estiverem presentes;
- branch não seguir convenção.

### CODEOWNERS

Definir responsáveis por:

- `.github/workflows/**`;
- `docs/adr/**`;
- `docs/governanca/**`;
- `config/**`;
- `src/**`.

---

## Resposta a merge prematuro

Quando ocorrer merge prematuro:

1. Registrar incidente no PR ou issue.
2. Verificar commit de merge.
3. Validar CI pós-merge.
4. Criar hotfix se houver falha.
5. Documentar causa raiz.
6. Adicionar ou reforçar guardrail.
7. Atualizar monitoramento operacional.

---

## Decisão

A partir deste registro, o padrão oficial do ReqSys passa a ser: merge só acontece após CI verde, revisão, saída intencional de draft e confirmação final.
