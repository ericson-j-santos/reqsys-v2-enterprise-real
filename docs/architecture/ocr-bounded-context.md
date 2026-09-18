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

## Origem Redmine

Anexos de issues do Redmine podem alimentar o mesmo bounded context sem criar um segundo motor OCR:

```text
Redmine issue + attachments
 -> valida origem / tamanho / extensão / assinatura binária
 -> SHA-256
 -> materialização sanitizada em OCR_INPUT_ROOT/redmine/<issue_id>/
 -> claim distribuído por job_id
 -> OCR_DOCUMENTO_SOLICITADO
 -> OcrWorker
```

Contrato operacional:

- endpoint governado: `POST /v1/ocr/redmine/issues/{issue_id}/attachments`;
- autenticação: administrador ReqSys, como os demais endpoints de processamento OCR;
- formatos aceitos neste incremento: PDF, PNG, JPEG, TIFF e BMP;
- anexos Office/ZIP ou outros formatos são classificados como `IGNORADO_FORMATO` e não são enviados ao Tesseract;
- `content_url` deve permanecer na mesma origem de `REDMINE_BASE_URL`, inclusive após redirect, reduzindo risco de SSRF e evitando vazamento da chave da API;
- `OCR_REDMINE_MAX_BYTES` limita o tamanho aceito; padrão: 25 MiB;
- a extensão declarada precisa ser compatível com a assinatura binária mínima do arquivo;
- o nome original do arquivo não compõe `document_ref`, evitando persistência desnecessária de PII em paths/logs;
- o conteúdo é identificado por SHA-256 e gravado atomicamente em caminho determinístico;
- o `job_id` usa `issue_id + attachment_id + SHA-256`;
- antes do OCR, `ocr_job_claims` concede um lease exclusivo ao primeiro consumidor; outra instância recebe `EM_PROCESSAMENTO` e não executa o OCR;
- `OCR_JOB_CLAIM_LEASE_SECONDS` controla o lease, com padrão de 600 segundos;
- crash ou término abrupto não mantém lock eterno: após a expiração do lease outro consumidor pode assumir o mesmo `job_id`;
- a liberação exige o mesmo `owner_token`, evitando que uma instância libere claim alheio;
- a persistência final continua protegida por `UNIQUE(job_id)` como segunda barreira contra duplicidade;
- anexo inválido entra no resultado como `QUARENTENA`; falha parcial é retornada como erro fail-closed;
- a PII extraída continua protegida pelo mesmo store AES-256-GCM e pela revisão governada já existente.

O adaptador usa `REDMINE_BASE_URL` e `REDMINE_API_KEY` pelo mecanismo central de secrets; credenciais não são persistidas em payload, log ou artifact.

## Benchmark

PR CI mede CER, Exact Match e False AUTO. Smoke: Exact Match >= 90%, CER <= 2%, False AUTO = 0. Gate completo alvo: Exact Match >= 98%, CER <= 0,5%, False AUTO <= 0,1% e zero False AUTO no corpus adversarial crítico.

`benchmark/ocr/datasets-v1.json` versiona fontes. MIDV-2020 exige aceite de licença; XFUND declara CC BY-NC-SA 4.0; FUNSD restringe uso a pesquisa/educação não comercial. Por isso não são baixados automaticamente em CI corporativo. O IBGE pode gerar snapshot explícito:

```bash
python scripts/ocr_benchmark.py fetch-ibge --destination benchmark/ocr/ibge-nomes-snapshot.json
```

O snapshot é vocabulário de geração sintética, nunca dicionário corretivo.
