# Public Runtime Evidence Gate

## Objetivo

Criar uma evidência operacional recorrente e acionável da disponibilidade pública do ReqSys, sem executar deploy, sem alterar secrets e sem depender de aprovação humana.

Este gate complementa o runtime Fly P0 já versionado e transforma a URL pública em sinal objetivo para o Estado Único ReqSys.

## Decisão arquitetural vigente

O contrato `strict` público deve validar somente endpoints de disponibilidade operacional canônica.

Endpoints de UX pública, contratos JSON, métricas e dashboard operacional não são critérios obrigatórios do gate público `strict`; devem ser tratados como evidência opcional, gates próprios, internos ou protegidos.

## Escopo

O workflow `.github/workflows/public-runtime-evidence.yml` executa validação read-only contra a API pública e publica artifact com:

- `public-runtime-validation.json`;
- `public-runtime-summary.md`.

Opcionalmente, em execução manual, o workflow também pode publicar o resumo como comentário em uma issue ou PR informado pelo operador.

## Endpoints mínimos validados em strict

Por padrão, o workflow reaproveita `scripts/validate_public_runtime.py` e valida somente:

```text
GET /health
GET /api/runtime/health
GET /api/runtime/readiness
GET /api/runtime/liveness
```

## Evidência pública opcional

Quando `--include-optional-evidence` está ativo, os endpoints abaixo também são coletados no artifact, mas não bloqueiam o `strict gate`:

```text
GET /
GET /runtime
GET /api/runtime/contracts
GET /api/runtime/version
GET /api/runtime/build-info
GET /api/runtime/dependencies
GET /api/runtime/metrics
GET /api/runtime/dashboard
```

Tratamento recomendado:

- `/`: evidência opcional de UX ou landing pública;
- `/runtime`: página operacional navegável;
- `/api/runtime/contracts`: contrato JSON versionado;
- `/api/runtime/version`: versão pública do runtime;
- `/api/runtime/build-info`: evidência de build/deploy;
- `/api/runtime/dependencies`: matriz pública simplificada de dependências;
- `/api/runtime/metrics`: endpoint interno, protegido ou validado por gate de observabilidade;
- `/api/runtime/dashboard`: endpoint interno, protegido ou validado por gate operacional autenticado.

## Execução manual sem comentário

```bash
gh workflow run "Public Runtime Evidence Gate" \
  -f public_url="https://reqsys-api.fly.dev" \
  -f strict=true \
  -f publish_comment=false
```

## Execução manual com comentário governado

```bash
gh workflow run "Public Runtime Evidence Gate" \
  -f public_url="https://reqsys-api.fly.dev" \
  -f strict=true \
  -f publish_comment=true \
  -f issue_number="<numero-da-issue-ou-pr>"
```

Use `issue_number` para publicar a evidência no PR, issue operacional ou issue de Estado Único ReqSys que precise receber o resumo.

## Execução recorrente

O workflow roda a cada 6 horas por `schedule` para produzir sinal operacional contínuo.

A execução recorrente não publica comentários automaticamente para evitar ruído operacional.

## Critério de sucesso

| Critério | Estado esperado |
|---|---|
| Workflow | `success` |
| Artifact | `public-runtime-evidence` publicado |
| `success_percentual` | `100.0` para endpoints strict |
| Endpoints mínimos strict | Todos HTTP 2xx |
| Endpoints opcionais | Não bloqueiam o gate público |
| Secrets | Nenhum valor exposto |
| Deploy | Não executado |
| Comentário | Apenas quando `publish_comment=true` e `issue_number` preenchido |

## Modo strict

Com `strict=true`, qualquer endpoint canônico público obrigatório com erro faz o workflow falhar.

Com `strict=false`, o artifact ainda é publicado para diagnóstico sem travar o workflow.

## Publicação de comentário

A publicação de comentário é controlada por input explícito e usa somente `GITHUB_TOKEN` com permissão mínima `issues: write`.

O comentário publica apenas `public-runtime-summary.md`, sem tokens, secrets, JWT, client secret ou PII.

Caso a política do repositório bloqueie `addComment` para o `GITHUB_TOKEN`, a evidência permanece disponível no artifact e a publicação governada deve ser reavaliada com GitHub App/token apropriado.

## Uso no Estado Único ReqSys

Este gate alimenta diretamente:

- deploy/URL pública;
- evidências críticas;
- progresso de produção;
- confiança operacional;
- risco operacional;
- decisão de consolidar ou não produção.

## Limites

Este gate não:

- cria app Fly;
- aplica secrets;
- executa deploy;
- corrige DNS;
- altera autenticação;
- substitui validação E2E de login Microsoft;
- comenta automaticamente em execuções agendadas;
- substitui gates internos de métricas, dashboard ou observabilidade autenticada.

## Próxima evolução recomendada

Após estabilização da publicação governada, integrar o resumo ao painel operacional interno do ReqSys ou ao índice executivo de evidências de produção.
