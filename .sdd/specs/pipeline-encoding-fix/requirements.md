# Requirements — pipeline-encoding-fix

> Reconstruido em 2026-08-16 a partir de evidencia real (commits + codigo atual). O `tasks.md`
> original referenciado no commit `0c4365b7` nao foi versionado e nao pode ser recuperado —
> os requisitos abaixo sao inferidos das docstrings de teste ("Req 3 e 2.3 (spec
> pipeline-encoding-fix)", em `backend/tests/test_pipeline.py:305`) e do comportamento
> efetivamente implementado. Numeracao "Requirement 3" preservada porque aparece literalmente
> no codigo; Requirements 1 e 2 foram atribuidos aos dois commits que os precedem.

## Requirement 1 — Verificacao anti-mojibake no CI

**User story:** Como mantenedor do backend, quero que o CI rejeite automaticamente qualquer
commit com strings mal decodificadas (mojibake), para que erros de encoding nunca cheguem a
producao silenciosamente.

**Acceptance criteria:**
1. QUANDO o pipeline de CI roda ENTAO o sistema DEVE escanear `app/api/` e `app/services/`
   por padroes de mojibake conhecidos (`Ã§`, `Ã£`, `Ã©`, `Ã¡`, `Ãº`).
2. SE algum padrao for encontrado ENTAO o CI DEVE falhar (`exit 1`) com o arquivo:linha do hit.
3. O mesmo check DEVE existir tambem como script standalone reexecutavel localmente
   (`scripts/check_encoding.py`), nao apenas embutido no workflow.

*Status: implementado — `.github/workflows/ci.yml:251-258` e `scripts/check_encoding.py`.*

## Requirement 2 — Eliminar regressao de teste duplicado

**User story:** Como desenvolvedor, quero que a suite de testes realmente execute a validacao
de encoding, para que uma classe de teste "sombra" (nunca executada) nao mascare uma regressao.

**Acceptance criteria:**
1. QUANDO duas classes com o mesmo nome existem no mesmo modulo de teste ENTAO apenas a ultima
   e executada pelo pytest (comportamento do Python) — o sistema NAO DEVE depender disso por
   acidente.
2. O modulo `test_pipeline.py` DEVE conter uma unica definicao de `TestEncodingRegressao`.

*Status: implementado — commit `0c4365b7` removeu a duplicata (linhas 193-239 antigas).*

## Requirement 3 — Respostas de erro da API em UTF-8 correto

**User story:** Como consumidor da API de pipeline/backlog, quero que mensagens de erro
acentuadas (ex.: "Integração desabilitada") cheguem corretas, para nao ver texto corrompido
tipo "IntegraÃ§Ã£o desabilitada".

**Acceptance criteria:**
1. QUANDO a flag `github_redmine_import_enabled` esta desligada e o cliente chama
   `POST /v1/integracoes/github/issues` ou `POST /v1/backlog/publicar-redmine/{id}` ENTAO o
   `detail` do erro 409 DEVE conter o termo "Integração" com acentuacao correta.
2. O `detail` NAO DEVE conter a sequencia `Ã` (assinatura de mojibake).
3. A string DEVE sobreviver a um round-trip `encode('utf-8').decode('utf-8')` sem alteracao.
4. O `Content-Type` da resposta DEVE conter `application/json` (charset UTF-8 implicito do
   FastAPI/JSONResponse).

*Status: implementado — `backend/tests/test_pipeline.py::TestEncodingRegressao` (4 testes).*

## Gap conhecido

Nao ha evidencia de qual era o escopo COMPLETO original do spec (ex.: se havia Requirement 4+
cobrindo outros modulos alem de `app/api/pipeline.py`). O check de CI cobre todo `app/api/` e
`app/services/`, entao a protecao e mais ampla que os 3 requisitos documentados acima — mas isso
foi decisao de implementacao, nao requisito formalmente registrado em algum lugar recuperavel.
