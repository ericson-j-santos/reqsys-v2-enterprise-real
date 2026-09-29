# Codex — cloud primário com fallback local

## Requisito 1 — primário
No Desktop, `gemma4:31b-cloud` deve permanecer como modelo primário dos providers Ollama direto e gateway.

## Requisito 2 — fallback
`gemma4:26b-q8-code` deve ser configurável como fallback local e usado somente quando a tentativa do modelo primário falhar por erro HTTP/rede do provider.

## Requisito 3 — evidência
O gateway deve devolver:
- `requested_model`: modelo solicitado;
- `model`: modelo efetivamente usado;
- `fallback_used`: se houve fallback.

## Requisito 4 — propagação
O backend ReqSys deve propagar `CODEX_OLLAMA_FALLBACK_MODEL` tanto para o provider direto quanto para o `ollama_gateway`.

## Requisito 5 — segurança e escopo
A configuração persistente deve permanecer no perfil local do Windows, sem editar `.env`, sem segredos e sem deploy/promoção de ambiente.

## Critérios de aceite
1. Primário cloud funciona no E2E real.
2. Controle negativo de cloud indisponível aciona o 26B local.
3. Modelo efetivo e uso de fallback são observáveis.
4. Testes unitários cobrem fallback direto, payload do gateway, resposta do gateway e persistência Windows.
5. Nenhuma chamada E2E publica payload no ReqSys nem toca produção.

## Requisito 6 — execução governada
A validação runtime deve executar somente em `DESKTOP-PDQK954`, ambiente DEV, por workflow self-hosted allowlisted `.github/workflows/codex-ollama-e2e-dev.yml`. A execução deve:
- usar o SHA exato despachado pelo GitHub;
- gerar `correlation_id` único por run/attempt;
- persistir artifact sanitizado de evidência;
- comprovar primário cloud e controle negativo de fallback local;
- não publicar no ReqSys, não executar deploy e não tocar produção;
- falhar fechado e cancelar o run exato quando o runner não fizer pickup.

## Critérios adicionais de aceite
6. O E2E runtime rejeita checkout cujo HEAD diverge do SHA esperado.
7. O artifact registra o mesmo SHA/correlation_id observado na chamada ReqSys.
8. A rota autorizada aceita somente `/reqsys run codex-ollama-e2e-dev`, sem inputs arbitrários.
9. Ausência de pickup termina com `SELF_HOSTED_RUNNER_UNAVAILABLE` e limpeza da fila, sem retry automático.

## Requisito 7 — benchmark CHANGE vinculado à PR #2144
O executor Ollama pode executar o benchmark de análise de impacto da PR #2144 somente pela rota exata `/reqsys run change-impact-benchmark-pr2144`. O comentário não recebe SHA, branch, workflow ou modelo como parâmetro.

O Authorized Actions Gateway deve resolver o `merge_commit_sha` diretamente de `pulls/2144` e falhar fechado se a PR não estiver fechada e efetivamente mergeada, se a base não for `main`, se o repositório de origem divergir ou se a branch não for exatamente `copilot/change-impact-benchmark-20260928`.

O workflow `codex-ollama-e2e-dev.yml` deve revalidar as mesmas invariantes antes do checkout, executar `scripts/change_impact_benchmark.py --llm-mode configured --provider ollama_gateway --require-llm` no SHA resolvido e publicar artifact sanitizado contendo SHA observado, digest SHA-256 do benchmark e confirmação de que o LLM foi usado em todos os casos híbridos.

## Critérios adicionais de aceite
10. Nenhum SHA arbitrário pode ser fornecido no comentário autorizado; o único SHA aceito é o `merge_commit_sha` devolvido pela API para a PR #2144 mergeada.
11. O checkout deve ser exatamente o HEAD atual da PR #2144 e o readback de `git rev-parse HEAD` deve coincidir.
12. O benchmark deve falhar se qualquer caso híbrido não tiver `llm_status=used`.
13. A evidência runtime deve registrar `target_sha`, `observed_sha`, `benchmark_sha256`, `production_touched=false` e `deploy_performed=false`.

