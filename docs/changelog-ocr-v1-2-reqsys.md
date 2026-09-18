# Changelog — OCR Evidência v1.2.0 no ReqSys

- fatia executável de reconhecimento de nomes do `ocr_evidencia` v1.2.0 incorporada;
- `OcrWorker` integrado ao Runtime Core por `OCR_DOCUMENTO_SOLICITADO`;
- estados técnicos e estados OCR permanecem separados;
- path traversal bloqueado por `OCR_INPUT_ROOT`;
- PII excluída da auditoria segura;
- Docker recebe Tesseract português, Poppler e ImageMagick;
- benchmark CI criado com CER, Exact Match e False AUTO;
- manifesto versionado de fontes públicas com downloads restritos por licença.

Nenhum endpoint público existente é alterado neste incremento.
