# Research — pipeline-encoding-fix

> Reconstruido em 2026-08-16. O research.md original nao e recuperavel; este documento registra
> apenas o raciocinio inferivel do padrao de bug corrigido, para dar contexto a quem ler o spec.

## O que e o bug (mojibake)

As sequencias detectadas (`Ã§`, `Ã£`, `Ã©`, `Ã¡`, `Ãº`, `Ã³`) sao a assinatura classica de uma
string UTF-8 correta que foi **decodificada como Latin-1/cp1252 e depois re-codificada como
UTF-8** (double-encoding). Exemplo concreto do proprio caso:

- Byte-correto UTF-8 de "ç" = `0xC3 0xA7`
- Se esses 2 bytes forem lidos como Latin-1, viram os caracteres "Ã" (U+00C3) + "§" (U+00A7)
- Se essa string de 2 caracteres for salva/serializada de novo como UTF-8, o resultado visivel
  e literalmente "Ã§" em vez de "ç" — e essa e a sequencia que o script cata.

Causa raiz tipica desse padrao (nao confirmada especificamente para este caso, mas e o cenario
canonico): arquivo `.py` fonte editado/salvo com um editor ou terminal configurado para
Latin-1/cp1252 em vez de UTF-8, ou um pipe intermediario (ex. Windows console codepage) que
reinterpreta bytes UTF-8 com a codepage errada antes de persistir a string literal no codigo.

## Por que a deteccao e por substring simples

Alternativas descartadas (implicitamente, pela escolha do design atual):

- **Biblioteca `ftfy`** ("fixes text for you") — resolveria e ate autocorrigira mojibake de
  forma generica, mas adiciona dependencia externa so para um CI check.
- **Validacao de round-trip em todos os literais de string do AST** — mais robusto (pegaria
  qualquer mojibake, nao so os 6-8 padroes listados), mas signficativamente mais complexo de
  implementar corretamente (strings f-string, concatenacao, etc.).

A escolha feita — grep por assinatura conhecida — cobre o caso real observado (acentos
portugueses comuns) com custo de implementacao minimo, ao preco de nao pegar mojibake fora da
lista de padroes (ex. sequencias geradas por outras codepages, ou line-endings/BOM corrompidos).

## Referencia cruzada com CLAUDE.md do usuario (ADR-002)

O ADR-002 (LGPD/PII) do usuario exige mascaramento correto de dados sensiveis nos logs (CPF,
e-mail, token). Mojibake em strings de log/erro e um risco correlato: se o mascaramento
(`***.456.789-**`) for aplicado sobre uma string ja corrompida por encoding, o padrao de
mascaramento pode nao casar e vazar o dado sem mascara. Isso nao esta testado explicitamente
neste spec, mas e uma razao adicional (nao documentada no codigo) para o check ser rigoroso.
