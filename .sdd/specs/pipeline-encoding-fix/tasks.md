# Tasks — pipeline-encoding-fix

> Reconstruido em 2026-08-16. Lista de tasks originais (numeracao "2.1"/"2.2" citada no commit
> `0c4365b7`) nao e recuperavel na integra — reconstruida a partir dos commits reais que a
> implementaram. Pode haver tasks originais sem rastro em commit (ex.: revertidas antes do
> commit final) que nao aparecem aqui.

- [x] **1.1** Criar script standalone de verificacao anti-mojibake
      (`scripts/check_encoding.py`) escaneando `app/api/` e `app/services/`
      _Commit: `6404238d`_
- [x] **1.2** Adicionar step de verificacao anti-mojibake no workflow de CI
      (`.github/workflows/ci.yml`, antes da execucao dos testes)
      _Commit: `6404238d`_
- [x] **2.1** Remover classe `TestEncodingRegressao` duplicada em `test_pipeline.py`
      (a primeira definicao, linhas 193-239, nunca era executada — Python so roda a ultima
      classe com o mesmo nome no modulo)
      _Commit: `0c4365b7`_
- [x] **2.2** Consolidar os testes de regressao de encoding na definicao final de
      `TestEncodingRegressao`, cobrindo os requisitos da spec
      _Commit: `0c4365b7`_
- [x] **2.3** Cobrir explicitamente round-trip UTF-8 e `Content-Type` charset nos testes
      (`test_response_decodifica_utf8_sem_erro`, `test_content_type_charset_utf8`)
      _Verificado presente em `backend/tests/test_pipeline.py:326-340` em 2026-08-16_

## Verificacao ao vivo (2026-08-16)

- `python scripts/check_encoding.py` → `OK — 137 arquivo(s) verificado(s), nenhum mojibake
  encontrado.`
- Step do CI (`.github/workflows/ci.yml:251-258`) presente e ativo na branch atual.

## Pendente / nao verificado

- [ ] Nenhuma task pendente conhecida — todas as tasks com evidencia em commit estao
  implementadas e verificadas. **Ressalva:** nao ha garantia de que esta e a lista completa do
  escopo original (ver nota no topo do arquivo). Se o usuario tiver o `tasks.md` original em
  outro lugar (backup, outra maquina), vale comparar.
- [ ] Divergencia entre `scripts/check_encoding.py` (Python) e o step inline do CI (`grep -E`
  no YAML) nao esta coberta por nenhum teste que garanta que os dois permanecem sincronizados
  (ver `design.md` → Riscos).
