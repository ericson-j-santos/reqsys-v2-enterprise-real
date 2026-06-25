# Runbook — Product Intelligence Final Evidence Index

## Objetivo operacional

Orientar a validação do índice final de evidências de Product Intelligence sem depender de inferências manuais ou de números fixos de PR.

## Quando usar

Use este runbook quando houver necessidade de confirmar se a frente de Product Intelligence possui evidência suficiente para avançar de documentação governada para validação operacional, homologação ou produção.

## Entradas mínimas

- PR ativo do incremento atual.
- SHA do head do PR.
- Estado de `mergeable` no momento da decisão.
- Conclusões dos workflows de CI e governança.
- Reviews e review threads.
- Artifacts publicados pelos workflows disponíveis.
- Evidência pós-merge na `main`, quando aplicável.

## Procedimento

1. Recapturar PRs abertos no GitHub.
2. Selecionar o PR relevante por prioridade operacional, sem número fixo.
3. Validar se existe PR equivalente para Product Intelligence Final Evidence Index.
4. Validar CI/checks/workflows no head SHA selecionado.
5. Confirmar `mergeable=true` e ausência de conflito.
6. Confirmar ausência de requested changes e threads não resolvidas.
7. Registrar artifacts disponíveis ou justificar `not_applicable`.
8. Remover draft apenas se os gates objetivos estiverem satisfeitos.
9. Realizar merge somente quando branch protection e permissões permitirem.
10. Após merge, validar checks na `main` e registrar regressões, se houver.

## Critérios de bloqueio

Bloqueie a promoção quando qualquer condição abaixo ocorrer:

- CI vermelho ou inconclusivo em workflow bloqueante.
- PR em draft sem evidência suficiente para ready-for-review.
- `mergeable=false` ou conflito detectado.
- Branch protection recusando merge.
- Review thread pendente ou requested changes ativo.
- Ausência de artifact crítico sem justificativa.
- Gate de segurança falho.
- Deploy/regressão pós-merge quebrado.

## Evidência final

A evidência final deve apontar para:

- PR do incremento;
- SHA de merge, quando existir;
- execução dos workflows no PR;
- execução dos workflows na `main` após merge;
- artifacts JSON/Markdown/HTML quando publicados;
- riscos residuais e próximos passos.

## Rollback

Como este incremento é documental/governança:

1. Reverter o PR via GitHub se houver impacto indevido.
2. Abrir PR corretivo pequeno.
3. Não remover branch protection.
4. Não alterar secrets.
5. Não executar deploy corretivo sem gate explícito.

## Saída operacional

A saída deve conter percentuais estimados de:

- progresso técnico;
- progresso operacional;
- progresso para usuário final;
- governança;
- produção;
- confiança;
- risco operacional.
