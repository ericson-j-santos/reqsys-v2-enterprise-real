# Design — pipeline-encoding-fix

> Reconstruido em 2026-08-16 a partir do codigo efetivamente implementado (nao ha design.md
> original recuperavel). Descreve o COMO tal como existe hoje no repositorio.

## Visao geral

Duas camadas independentes e redundantes de protecao contra mojibake, mais uma suite de
testes de regressao focada nas respostas HTTP da API de pipeline:

```
┌─────────────────────────────┐      ┌──────────────────────────────┐
│ .github/workflows/ci.yml     │      │ scripts/check_encoding.py     │
│ step "Verificar encoding     │      │ (mesma logica, standalone,    │
│ UTF-8 (anti-mojibake)"       │      │ executavel local antes do PR) │
│ grep inline -E               │      │ scan() por Path.rglob("*.py") │
└──────────────┬────────────────┘      └───────────────┬────────────────┘
               │                                        │
               └──────────────┬─────────────────────────┘
                               ▼
              falha (exit 1) se encontrar Ã§ Ã£ Ã© Ã¡ Ãº Ã³ ...
                     em app/api/ e app/services/

┌──────────────────────────────────────────────────────────┐
│ backend/tests/test_pipeline.py::TestEncodingRegressao     │
│ 4 testes: mensagem correta, ausencia de "Ã", round-trip   │
│ UTF-8, Content-Type — cobrindo os 2 endpoints que usam    │
│ a string "Integração" em HTTPException.detail             │
└──────────────────────────────────────────────────────────┘
```

## Decisoes de design

1. **Deteccao por substring, nao por biblioteca (ex.: `ftfy`)** — o script usa uma lista fixa
   de padroes (`Ã§`, `Ã£`, `Ã©`, `Ã¡`, `Ãº`, `Ã³`, `Ã\xad`, `Ã\xa3`) em vez de heuristica de
   biblioteca de deteccao de mojibake. Trade-off: simples e sem dependencia nova, mas so
   detecta os padroes de double-encoding UTF-8→Latin-1/cp1252 explicitamente listados — nao e
   uma deteccao generica.
2. **Duplicacao intencional CI inline + script standalone** — o step do CI usa `grep -rn` em
   shell diretamente (nao chama `scripts/check_encoding.py`), o que significa que os dois
   precisam ser mantidos em sincronia manualmente se a lista de padroes mudar. Isso e uma
   divergencia de design que vale endereçar (ver Riscos).
3. **Escopo do scan limitado a `app/api/` e `app/services/`** — nao cobre `app/core/`,
   `app/models/`, migrations ou frontend. Decisao implicita (nao documentada) de que mojibake
   em respostas HTTP visiveis ao usuario e o risco prioritario.

## Riscos / divergencias identificadas

- `scripts/check_encoding.py` tem `DEFAULT_TARGETS` identicos ao step do CI, mas sao duas
  implementacoes separadas (uma em Python, outra em `grep -E` no YAML). Se a lista de padroes
  mojibake for atualizada em um lugar, pode ficar desatualizada no outro — nenhum teste garante
  que os dois ficam em sincronia.
