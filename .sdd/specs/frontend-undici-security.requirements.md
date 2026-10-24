# Segurança frontend — undici GHSA-xjj6-f33q-929c

## Diagnóstico

A execução #40105884922 do ReqSys falhou em `npm audit --audit-level=high`
porque `frontend/package.json` forçava `overrides.undici=7.30.0`.
O `package-lock.json` continha a mesma versão, resolvida como dependência
de `jsdom` (intervalo `^7.25.0`). O SHA original da main e da PR continha
o mesmo lock vulnerável. O advisory GHSA-xjj6-f33q-929c indica `7.30.1`
como o menor patch da série 7.x.

## Critérios de aceite

1. Alterar exclusivamente o override e a entrada transitiva do lock para
   `undici@7.30.1` com URL do npm Registry e integridade SHA-512.
2. `npm ci` deve instalar o grafo congelado sem alteração automática e
   `npm ls undici` deve confirmar a versão resolvida.
3. `npm audit --audit-level=high` precisa aprovar sem supressão ou bypass.
4. `npm run build`, testes de segurança e CI principal precisam executar de fato.
5. `tests/test_frontend_undici_security_lock.py` verifica consistência do
   override/lock e rejeita regressão `7.30.0` e ausência de integridade.
6. Revalidar o OCR Benchmark Gate e o PR Evidence Gate no novo HEAD.
7. Preservar `backend/ocr_evidencia` e o SHA do motor OCR; sem merge,
   deploy, produção, promoção ou alteração de credenciais.

## Rollback

Se ocorrer regressão, realizar commit compensatório na mesma PR e manter
`npm audit` obrigatório; não aceitar retornar a `7.30.0` sem corrigir a
vulnerabilidade. A alteração permanece em draft até os gates aprovarem.
