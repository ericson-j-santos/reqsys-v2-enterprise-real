# OCR v2 — armazenamento protegido, revisão humana e corpus governado

## Estado alvo

O bounded context OCR do ReqSys processa documentos por referência relativa, persiste o resultado sensível criptografado, envia somente resultados não-AUTO para revisão humana e mede regressão por CER, Exact Match e False AUTO.

## Fluxo

```text
OCR_INPUT_ROOT/document_ref
        |
        v
OcrWorker -> ocr_evidencia/Tesseract multipass
        |
        v
AES-256-GCM -> ocr_resultados
        |
        +-- AUTO --------------------> concluído sem fila humana
        |
        +-- demais estados ----------> PENDENTE
                                        |
                                        v
                              /admin/ocr-review
                              APROVADO | REJEITADO
```

## Segurança

- `OCR_DATA_ENCRYPTION_KEY` é obrigatória e deve representar 32 bytes codificados em Base64.
- A chave é resolvida pelo mecanismo central de secrets/vault do ReqSys; não deve ser commitada.
- `OCR_DATA_KEY_VERSION` identifica a versão ativa da chave para futura rotação/recriptografia.
- O valor reconhecido e os motivos de baixa confiança ficam em `payload_protegido` com AES-256-GCM e AAD = `job_id`.
- A observação da decisão humana também é criptografada.
- A identidade do revisor é armazenada apenas como SHA-256.
- Listagens retornam somente metadados; PII só é revelada no detalhe autenticado da revisão.
- Sem chave ou sem `OCR_INPUT_ROOT`, o processamento fica fail-closed.

## Endpoints

Todos exigem administrador autenticado:

- `GET /v1/ocr/readiness`
- `POST /v1/ocr/jobs`
- `GET /v1/ocr/review?status=PENDENTE`
- `GET /v1/ocr/review/{job_id}`
- `POST /v1/ocr/review/{job_id}/decision`

## Blueprint humano mínimo — habilitar runtime

### Pré-requisitos

1. Definir um diretório privado para entrada OCR e montar/fornecer esse diretório ao backend.
2. Ter acesso autorizado ao cofre/secret store do ambiente.

### Ação

1. Gerar uma chave aleatória de 32 bytes fora do repositório.
2. Codificar a chave em Base64.
3. Gravar como secret `OCR_DATA_ENCRYPTION_KEY` no ambiente/cofre correto.
4. Definir `OCR_DATA_KEY_VERSION=v1`.
5. Definir `OCR_INPUT_ROOT` para o diretório privado de entrada.
6. Reiniciar/reimplantar o backend pelo fluxo governado normal.

Exemplo local de geração, sem imprimir a chave em logs de CI:

```bash
python -c "import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

### Validação/evidência

`GET /v1/ocr/readiness` deve retornar:

```json
{
  "ready": true,
  "encryption": "AES-256-GCM",
  "key_configured": true,
  "input_root_configured": true,
  "plaintext_storage_allowed": false
}
```

Critério de conclusão: readiness verde + processamento de uma amostra sintética + registro no banco sem ocorrência do valor reconhecido em plaintext.

## Datasets externos

`benchmark/ocr/datasets-v1.json` é a fonte de política. O executável `scripts/ocr_dataset_policy.py` bloqueia uso fora do contexto licenciado.

- IBGE/CIN: permitidos como metadados/referência para geração sintética.
- MIDV-2020, XFUND e FUNSD: bloqueados no `corporate-ci`.
- Em `research-noncommercial`, continuam bloqueados até existir aceite humano explícito dos termos aplicáveis.

## Corpus real/anônimo

Documentos reais não devem ser commitados. `scripts/ocr_real_corpus_policy.py` exige:

- corpus e manifesto fora do repositório;
- `approval_reference` preenchida;
- declaração explícita `contains_personal_data=false`;
- classificação `ANONYMIZED_APPROVED` ou `HOMOLOGATED_APPROVED`;
- hash SHA-256 por arquivo;
- caminho relativo sem traversal;
- extensão suportada.

O gate não copia nem publica o conteúdo. Quando uma amostra aprovada existir, suas métricas devem ser comparadas ao baseline sintético para quantificar o gap de produção.
