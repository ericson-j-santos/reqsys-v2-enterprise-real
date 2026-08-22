# OCR no ReqSys — bounded context e benchmark

## Decisão

O ReqSys governa **orquestração, correlation_id, retry/DLQ, auditoria e revisão**. O reconhecimento fica isolado na fatia executável do `ocr_evidencia` v1.2.0.

```text
RuntimeEventBus -> OCR_DOCUMENTO_SOLICITADO -> OcrWorker
 -> TesseractMultipass -> consenso por caractere
 -> AUTO | VALIDACAO_ADICIONAL | REVISAO | ABSTENCAO
```

O estado OCR não substitui o estado técnico do runtime: falha técnica segue retry/DLQ; baixa confiança é resultado válido do domínio.

## Segurança

- `document_ref` é relativo a `OCR_INPUT_ROOT`; path traversal e caminho absoluto são rejeitados.
- nome reconhecido é PII e não entra em `auditoria_sem_pii()`.
- repositório in-memory é somente DEV/teste; produção requer store sensível com criptografia/RBAC/retenção.
- IBGE ou outra lista de nomes nunca é usada para autocorreção.

## Benchmark

PR CI mede CER, Exact Match e False AUTO. Smoke: Exact Match >= 90%, CER <= 2%, False AUTO = 0. Gate completo alvo: Exact Match >= 98%, CER <= 0,5%, False AUTO <= 0,1% e zero False AUTO no corpus adversarial crítico.

`benchmark/ocr/datasets-v1.json` versiona fontes. MIDV-2020 exige aceite de licença; XFUND declara CC BY-NC-SA 4.0; FUNSD restringe uso a pesquisa/educação não comercial. Por isso não são baixados automaticamente em CI corporativo. O IBGE pode gerar snapshot explícito:

```bash
python scripts/ocr_benchmark.py fetch-ibge --destination benchmark/ocr/ibge-nomes-snapshot.json
```

O snapshot é vocabulário de geração sintética, nunca dicionário corretivo.
