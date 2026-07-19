# Pendência — Vulnerabilidades de dependências (Dependabot, 2026-07-19)

Status: **PARCIALMENTE RESOLVIDO** — correções seguras aplicadas; 2 itens
ficam pendentes por exigirem migração major.

Contexto: GitHub reportou 97 alertas do Dependabot no branch padrão
(`main`). O token usado neste repositório não tem permissão de leitura de
"Dependabot alerts" (`gh api .../dependabot/alerts` retornou 403), então a
varredura foi feita localmente por ecossistema com `pip-audit`, `npm audit` e
`dotnet list package --vulnerable` — mesma base de dados de advisories
(GitHub Advisory Database/OSV), resultado equivalente.

## Resolvido

| Manifest | Antes | Depois | Como |
| --- | --- | --- | --- |
| `requirements-docs.txt` | `pymdown-extensions==10.16` (2 CVEs) | `==10.21.3` | bump direto |
| `runtime/requirements.txt` | `pytest>=8.2.0,<9.0.0` (CVE, upper bound excluía o fix) | `>=9.0.3,<10.0.0` | ampliar range |
| `examples/monitorador_apis_python/requirements.txt` | `aiohttp==3.9.5` (30+ CVEs), `fastapi==0.111.0`→`starlette` 0.37.2 vulnerável (transitivo), `pytest==8.2.2` | `aiohttp==3.14.1`, `fastapi==0.137.2` (puxa `starlette>=1.3.1`), `pytest==9.0.3`, `pytest-asyncio==1.3.0`, `pytest-cov==7.0.0` (bump necessário por conflito de resolução com o novo pytest) | bump direto |
| `backend-dotnet/tests/.../ReqSys.Api.Tests.csproj` | `System.Text.Json` transitivo em 8.0.0 (2 CVEs High) via `Microsoft.AspNetCore.Mvc.Testing` | pin direto `System.Text.Json 8.0.6` | `dotnet test`: 9/9 passou |
| `frontend-vuetify` | 10 vulns (2 crit/4 high/4 mod) | 6 restantes (ver abaixo) | `npm audit fix` (sem `--force`) — `brace-expansion`, `form-data`, `js-cookie`, `ws` corrigidos; só `package-lock.json` mudou |
| `frontend-angular` | 58 vulns (2 crit/32 high/20 mod/4 low) | 50 restantes (ver abaixo) | `npm audit fix` (sem `--force`) eliminou as 2 críticas (`shell-quote`, `websocket-driver`) sem tocar `package.json` |

`backend/requirements.txt`, `backend/requirements-audit.txt`,
`backend/requirements-rag.txt`, `frontend/package.json` (Vue) e o
`package.json` da raiz: **já estavam limpos**, nenhuma ação necessária.
`backend-dotnet/src/ReqSys.Api/ReqSys.Api.csproj`: já estava limpo.

Todos os testes automatizados relevantes rodaram depois das correções:
`pytest` no `backend` (1362 passed — 3 falhas pré-existentes e não
relacionadas, ver nota abaixo), `dotnet test` no `backend-dotnet` (9/9),
`vitest` no `frontend-vuetify` (79/79).

## Nota — 3 falhas pré-existentes encontradas no backend (não relacionadas)

Ao rodar a suíte completa do `backend` como sanity check, 3 testes falharam
em `tests/test_teams_gateway_flow_bot_multi_owner.py`. Confirmado via `git
diff --stat` que nenhuma mudança desta pendência tocou `backend/app` ou
`backend/tests` — são falhas preexistentes, fora do escopo desta correção de
vulnerabilidades. Registrar separadamente se for investigar.

## Pendente — decisão do usuário (2026-07-19): documentar, não migrar agora

### `frontend-vuetify` — vitest 2.1.9 → 4.1.10 (6 vulns, 2 críticas)

Tentativa feita e **revertida**: `npm install --save-dev vitest@4.1.10
@vitest/coverage-v8@4.1.10` zerou o `npm audit` (0 vulnerabilidades), mas
quebrou 3 das 5 suítes de teste (`TypeError: Unknown file extension ".css"`
ao importar componentes do Vuetify — mudança de como o vitest 4 resolve
CSS/ambiente `node` vs `jsdom`). Revertido via `git checkout --
package.json package-lock.json` e reaplicado só o `npm audit fix` seguro.

Vulnerabilidades restantes (todas em ferramental de teste/build, não
afetam o app publicado): `vitest`/`@vitest/coverage-v8` (crítico —
CVE de leitura/execução de arquivo arbitrário quando o UI server do Vitest
está rodando), `vite`, `vite-node`, `@vitest/mocker`, `esbuild`.

**Para retomar:** migrar para vitest 4 exige revisar a config de ambiente de
teste (`vitest.config`) para os specs que importam componentes Vuetify —
provavelmente trocar `environment: 'node'` por `'jsdom'`/`'happy-dom'` nesses
specs ou ajustar `deps.inline`/`server.deps.inline` (aviso de depreciação já
aparecia mesmo na v2). Tratar como migração dedicada, não bump solto.

### `frontend-angular` — Angular v18/19 → v22 (50 vulns, 30 altas)

Não tentado. Praticamente todo pacote `@angular/*`, `@angular-devkit/*` e
`@angular/cli` reporta `fixAvailable.isSemVerMajor: true` apontando para a
mesma versão-alvo (`22.0.x`) — ou seja, o fix real é um salto de **4 versões
major** do Angular de uma vez, não bumps independentes. Isso normalmente
exige rodar `ng update` major a major (18→19→20→21→22) com as migrations
automáticas de cada versão, mais correção manual de breaking changes de API
— escopo de migração de framework, não de patch de segurança.

CVEs de maior severidade nesse lote (todas cobertas pelo salto para v22):

- `@angular/core`, `@angular/compiler`: múltiplas XSS (i18n attribute
  bindings, SVG script/animation attributes, namespace sanitization bypass).
- `@angular/common`: XSRF token leakage via protocol-relative URLs, DoS por
  OOM em formatação de data/número, cache key hashing fraco no
  `HttpTransferCache`.
- `shell-quote`/`websocket-driver` (críticas) — **já corrigidas** pelo `npm
  audit fix` sem precisar do salto major.

**Para retomar:** tratar como projeto à parte — `ng update @angular/core
@angular/cli` uma versão major por vez, rodando build+testes entre cada
salto, antes de considerar `frontend-angular` pronto para produção.

## Segurança

Nenhum valor de secret foi tocado neste trabalho — só manifests de
dependência (`requirements*.txt`, `package.json`/`package-lock.json`,
`*.csproj`).

## Referências

- [cofre-operacional.md](cofre-operacional.md)
- `pip-audit`, `npm audit`, `dotnet list package --vulnerable` (ferramentas
  usadas para a varredura local)
