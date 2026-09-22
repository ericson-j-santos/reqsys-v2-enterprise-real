# OCR Public Corpus Technical Certification v1

## Objetivo

Executar regressão técnica semanal do OCR com documentos públicos verificáveis, sem converter essa execução em evidência institucional e sem autorizar promoção para produção.

## Limites de segurança

- somente fontes HTTPS em domínios explicitamente permitidos;
- somente arquivos PDF com até 25 MiB;
- `case_id` limitado a caracteres alfanuméricos, ponto, hífen e sublinhado, com no máximo 100 caracteres;
- IDs duplicados são recusados antes de qualquer download;
- cada arquivo certificado deve permanecer dentro da raiz do corpus, inclusive após resolução de links simbólicos;
- caminhos absolutos, `..`, arquivos ausentes e extensões diferentes de PDF falham de forma fechada;
- o relatório não contém texto OCR, texto esperado nem caminho do arquivo.

## Governança

Mesmo quando o gate técnico retorna `PASS`, os campos `institutional_validity`, `production_allowed` e `promotion_eligible` permanecem obrigatoriamente como `false`. A certificação institucional com corpus real anonimizado ou homologado continua sendo o fluxo separado descrito em `ocr-real-corpus-certification-v1.md`.

## Validação focada

```bash
cd backend
pytest -q ocr_tests/test_public_corpus_certify.py
```
