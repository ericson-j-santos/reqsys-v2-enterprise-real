# Ponte OCR de documentos de demanda — DEV

## Estado alvo deste incremento

`upload PDF/imagem -> PROCESSANDO_OCR -> texto por página -> candidatos -> AGUARDANDO_REVISAO_HUMANA`

Em falha, o estado é `ERRO_OCR`. Nenhum candidato é incorporado automaticamente.

## Ativação

A ponte é fail-closed e vem desabilitada. Ela só executa quando as duas condições forem verdadeiras:

1. `APP_ENV` resolve para desenvolvimento ou testes;
2. `DOCUMENTO_DEMANDA_OCR_ENABLED=true`.

Configuração opcional:

- `DOCUMENTO_DEMANDA_OCR_LANG=por`
- `DOCUMENTO_DEMANDA_OCR_DPI=200`
- `DOCUMENTO_DEMANDA_OCR_TIMEOUT_SECONDS=60`
- `DOCUMENTO_DEMANDA_OCR_MAX_PAGES=25`

Em homologação e produção, a ponte permanece desabilitada mesmo que a chave seja configurada por engano.

## Dependências de execução

A imagem Fly passa a conter Tesseract em português e Poppler (`pdftoppm`/`pdfinfo`). O endpoint administrativo `GET /v1/ocr/demandas/documentos/ocr-readiness` expõe apenas prontidão técnica, sem texto ou PII.

## Segurança e rastreabilidade

- arquivo temporário nomeado pelo SHA-256, não pelo nome original;
- permissões restritivas no diretório/arquivo quando suportadas pelo sistema operacional;
- limite de 10 MB herdado do upload e limite adicional de 25 páginas para PDF por padrão;
- referência de página e confiança preservadas em cada candidato;
- texto do documento não é enviado no payload do barramento;
- falhas do motor não devolvem o conteúdo do erro interno ao cliente;
- reenvio do mesmo `demanda_ref + SHA-256` reutiliza o registro e pode recuperar `ERRO_OCR` sem duplicação;
- incorporação automática permanece permanentemente `false` neste incremento.

## Transporte

O barramento atual do Runtime Core é produtor-consumidor síncrono e em memória, com retentativas e dead-letter. Este incremento reutiliza o contrato existente sem introduzir um broker externo. A migração futura para Redis Streams/outbox pode manter o mesmo evento `OCR_DOCUMENTO_DEMANDA_SOLICITADO`.
