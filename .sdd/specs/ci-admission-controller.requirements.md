# CI Admission Controller + Evidence Manifest

## Objetivo

Eliminar retrabalho recorrente descoberto tarde no CI, reutilizando o `Pre-PR Readiness Gate` como autoridade de admissão por SHA antes de iniciar suítes caras.

## Classificação

`gap_fix`.

## Estado de dependência

A degradação fail-closed da triagem Ollama já está integrada na `main`: falha de inferência ou saída estruturada inválida produz estado `OLLAMA_CI_TRIAGE_DEGRADED` sem autoescalonamento. Este incremento não duplica nem sobrescreve esse mecanismo; o manifesto apenas registra Ollama como acelerador opcional.

## Requisitos

1. O Pre-PR deve produzir `artifacts/admission/<head_sha>.json` com HEAD, base, perfis, workflows necessários, dependências, evidência e causas classificadas de bloqueio.
2. O artefato publicado deve se chamar `ci-admission-<head_sha>`.
3. CIs caros de PR (`CI — ReqSys v2 Enterprise`, `CI Enterprise Fast` e `CI E2E Governado`) devem validar o Admission Controller antes do roteador ou guardrail pesado.
4. O Admission Controller deve exigir um `Pre-PR Readiness Gate` concluído com sucesso e o artefato de admissão do mesmo SHA.
5. O HEAD admitido deve estar baseado na `base_ref` corrente, com `behind_by=0`; branch atrasada ou divergida deve falhar fechado.
6. O guard pode aguardar de forma limitada a conclusão do Pre-PR para evitar corrida entre eventos `push` e `pull_request`, nunca indefinidamente.
7. Push de `main`, `merge_group` e execução manual não devem ser bloqueados por ausência de manifesto de PR.
8. O PR Evidence Gate deve exigir `Pre-PR Readiness Gate` e o artefato `ci-admission-<head_sha>` não expirado do SHA atual.
9. Evidência de SHA antigo não pode liberar CI caro nem Evidence Gate.
10. Nenhum merge, deploy, promoção de ambiente, segredo ou escrita em branch protegida faz parte deste incremento.
11. O Pre-PR deve executar e registrar como invariantes preventivos obrigatórios: contrato SDD, segurança no diff e contratos de regressão de workflow.
12. O security gate antecipado deve limitar bloqueadores estáticos às linhas adicionadas/modificadas no HEAD, evitando que dívida legada não tocada gere falso positivo; achados contextuais continuam visíveis para revisão.
13. O manifesto de admissão deve carregar os invariantes preventivos e somente ficar `admitted` quando todos estiverem `passed`, `behind_by=0` e o SHA/base forem válidos.
14. O Admission Controller deve baixar o artifact `ci-admission-<head_sha>`, ler o JSON interno e validar schema, tipo, status, HEAD, base SHA e invariantes; validar apenas nome/metadado do artifact é insuficiente.
15. O download do artifact não pode encaminhar o bearer token do GitHub ao host externo do redirect assinado.

## Controles negativos

- Pre-PR ausente/falho no SHA atual => Admission Controller bloqueia o CI caro.
- Pre-PR ainda em execução => espera limitada; timeout mantém bloqueio.
- Artefato com SHA diferente ou expirado => bloqueio.
- `main` avançou e o branch ficou atrás/divergiu => `source_stale_or_diverged`.
- Evidence Gate sem manifesto do HEAD => falha.
- Artifact com nome correto, mas conteúdo de outro HEAD/base, schema inválido ou invariante faltante/falho => Admission Controller bloqueia.
- Dívida de segurança pré-existente em linha não alterada não bloqueia o Pre-PR; o mesmo sinal introduzido em linha nova bloqueia.
- Falha do Ollama permanece degradada/fail-closed pelo mecanismo já integrado na `main`, sem produzir nova falha de CI por si só.

## Critérios de aceite

- `tests/test_ci_admission_control.py` e `tests/test_pre_pr_readiness.py` verdes.
- Pre-PR Readiness verde no HEAD final, com `behind_by=0`.
- Artefato `ci-admission-<HEAD>` publicado pelo mesmo run/SHA.
- Caso negativo detecta SHA divergente, artefato expirado e base atrasada/divergida.
- Os três workflows caros têm dependência transitiva do job `ci-admission`.
- PR Evidence Gate rejeita ausência do manifesto do mesmo SHA.
- Manifesto preventivo contém `sdd:contract`, `security:changed-diff` e `workflow:regression-contracts` com status `passed`.
- Teste negativo prova que artifact com nome correto e conteúdo/base/invariante inválido é rejeitado.
- Teste negativo prova que o security gate distingue dívida legada não tocada de blocker introduzido no diff.
- `tests/test_vibe_security_gate.py` verde junto aos testes de admission/readiness.
- Nenhum merge/deploy executado por este incremento.


## Diagnóstico do gate agregado

Quando a consolidação Padrão Ouro não atingir a meta, o processo deve emitir diagnóstico estruturado dos artifacts ingeridos, eixos e domínios. Esse diagnóstico é somente observabilidade: não reduz limiares, não converte warning em sucesso e não substitui a correção da causa raiz.


## Escopo de ambientes

O detector de drift deve consumir `infra/public-access-urls.json` como contrato machine-readable do runtime atual. Ambientes com `runtime_target=not_promoted` não participam do comparativo obrigatório do incremento corrente. A ausência dessa fonte mantém o comportamento legado estrito. Se PROD mudar para um runtime ativo, configuração PROD vazia/ausente, healthcheck ausente, porta direta ou gates `APP_ENV/ALLOW_DEMO_LOGIN` inválidos voltam a bloquear automaticamente.
