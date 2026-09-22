# CI Admission Controller + Evidence Manifest

## Objetivo

Eliminar retrabalho recorrente de CI descoberto tarde, reutilizando o `Pre-PR Readiness Gate` como autoridade de admissão do SHA e tratando Ollama como acelerador opcional, nunca como autoridade de governança.

## Classificação

`gap_fix`.

## Problema evidenciado

A triagem Ollama falhou com `ollama_structured_output_invalid`, transformando uma ferramenta de diagnóstico em novo sinal vermelho. Em paralelo, workflows caros podiam iniciar sem comprovar previamente que o mesmo SHA tinha `READY_FOR_PR=passed`, e o Evidence Gate não exigia explicitamente o manifesto do SHA atual.

## Requisitos

1. O Pre-PR deve produzir `artifacts/admission/<head_sha>.json` com HEAD, base, perfis, workflows necessários, dependências, evidência e causas classificadas de bloqueio.
2. O artefato publicado deve se chamar `ci-admission-<head_sha>`.
3. CIs caros de PR (`CI — ReqSys v2 Enterprise`, `CI Enterprise Fast` e `CI E2E Governado`) devem validar, antes do roteador ou guardrail pesado, um Pre-PR concluído com sucesso e o artefato de admissão do mesmo SHA.
4. Push de `main`/execução manual não deve ser bloqueado por ausência de manifesto de PR.
5. Saída Ollama inválida, indisponível ou não estruturada deve degradar para classificação determinística; a execução não deve falhar apenas por indisponibilidade do acelerador.
6. Sinais determinísticos bloqueadores (`timeout`, `quota`, permissões, conflito e equivalentes) nunca podem ser convertidos em autocorreção técnica pelo fallback.
7. O PR Evidence Gate deve exigir `Pre-PR Readiness Gate` e o artefato `ci-admission-<head_sha>` não expirado do SHA atual.
8. Evidência de SHA antigo não pode liberar CI caro nem Evidence Closure.
9. Nenhum merge, deploy, promoção de ambiente, segredo ou escrita em branch protegida faz parte deste incremento.

## Controles negativos

- Pre-PR ausente/falho no SHA atual => Admission Controller bloqueia o CI caro.
- Artefato com SHA diferente ou expirado => bloqueio.
- `ollama_structured_output_invalid` => triagem determinística degradada, sem vermelho artificial.
- Sinal determinístico transitório/bloqueador => sem autoescalonamento para Worker Pool.
- Evidence Gate sem manifesto do HEAD => falha.

## Critérios de aceite

- `tests/test_ci_admission_control.py`, `tests/test_ollama_ci_triage.py`, `tests/test_ollama_ci_triage_workflow.py` e `tests/test_pre_pr_readiness.py` verdes.
- Pre-PR Readiness verde no HEAD final e artefato `ci-admission-<HEAD>` publicado.
- Caso negativo detecta SHA divergente/artefato expirado.
- A triagem Ollama com saída inválida termina em `OLLAMA_CI_TRIAGE_DEGRADED` com `triage_source=deterministic_fallback`.
- PR Evidence Gate rejeita ausência do manifesto do mesmo SHA.
- Nenhum merge/deploy executado por este incremento.
