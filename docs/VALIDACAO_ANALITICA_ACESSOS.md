# Validação analítica de acessos — ReqSys v2 Enterprise Real

## Objetivo

Consolidar os acessos públicos atualmente válidos, os critérios de validação operacional e a evidência pós-merge do runtime vigente.

## Estado de ambientes

| Ambiente | Estado | Entrada pública | Runtime |
| --- | --- | --- | --- |
| DEV | ativo | `https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/` | PC24x7 + Cloudflare Quick Tunnel resolvido por locator Ed25519 |
| HML | não promovido | sem endpoint público canônico ativo | `runtime_target=not_promoted` |
| PROD | não promovido | sem endpoint público canônico ativo | `runtime_target=not_promoted` |
| DEV local | ativo quando host disponível | `http://127.0.0.1:8083` | gateway Nginx local |

A fonte machine-readable é `infra/public-access-urls.json`. Referências históricas Fly.io não definem o runtime atual.

## Validação automatizada

Comando:

```bash
npm run validate:access
```

Script:

```text
scripts/validar-acessos-publicos.mjs
```

Workflow:

```text
.github/workflows/validacao-acessos.yml
```

## Gatilhos do workflow

| Gatilho | Quando executa | Comportamento |
| --- | --- | --- |
| `pull_request: closed` em `main` | Após qualquer PR realmente mergeada | Executa somente com `merged=true`, faz checkout do `merge_commit_sha` exato e valida com `fail_on_unavailable=true` |
| `push` em `main` | Fallback para push direto permitido pela governança | Validação bloqueante |
| `workflow_dispatch` | Execução manual | Permite escolher `fail_on_unavailable=true` ou `false` |
| `schedule` | Diariamente às 10:17 UTC | Validação bloqueante recorrente |

O workflow **não depende de `workflow_run`** para comprovar pós-merge. Isso evita corrida com automações de merge e elimina execuções `skipped` quando o merge é realizado via `GITHUB_TOKEN`.

## Governança

- Permissão mínima: `contents: read`.
- Concorrência: `validacao-acessos-${{ github.ref }}`.
- O checkout pós-merge usa explicitamente `github.event.pull_request.merge_commit_sha`.
- A execução falha fechado se o SHA observado divergir do SHA esperado.
- Evidência produzida por SHA anterior não pode liberar a validação pós-merge atual.
- O relatório é publicado como artifact `validacao-acessos-publicos` mesmo quando a validação encontra falha.
- O runtime DEV público obrigatório é a entrada estável `/dev/`, que resolve somente locator assinado vigente.

## Campos analíticos

O relatório JSON contém `generatedAt`, timeout, totais, alcançáveis, status esperados, indisponíveis, latência média/máxima, quebra por ambiente e evidência por URL.

## Critérios de aceite operacionais

| Critério | Regra |
| --- | --- |
| Entrada DEV estável | HTTP 200 na URL GitHub Pages `/dev/` |
| Runtime resolvido | Locator Ed25519 vigente, DEV, não expirado e limitado a HTTPS `*.trycloudflare.com` |
| API/runtime | Endpoints obrigatórios devem retornar HTTP 200 conforme contrato do publisher |
| SHA pós-merge | Checkout deve corresponder ao `merge_commit_sha` do PR fechado |
| Falha bloqueante | Pós-merge, push e schedule usam `ACCESS_VALIDATION_FAIL_ON_UNAVAILABLE=true` |
| HML/PROD | Não são exigidos enquanto `runtime_target=not_promoted` |

## Interpretação

- 100% alcançável e status esperado: acesso público íntegro para o escopo ativo.
- Entrada estável disponível, mas locator expirado/sem runtime: runtime DEV indisponível; não tratar Pages isoladamente como sucesso funcional.
- Runtime DEV falho: bloquear promoção e corrigir o PC24x7/Cloudflare antes de ampliar escopo.
- HML/PROD só entram na validação obrigatória após promoção explícita no manifesto de runtime.
