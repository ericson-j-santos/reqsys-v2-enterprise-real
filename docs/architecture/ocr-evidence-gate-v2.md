# OCR Evidence Gate v2

## Objetivo

Certificar, em CI, a leitura OCR de dez cenários documentais que representam os principais riscos do fluxo de documentos do ReqSys sem publicar dados pessoais reais.

O gate complementa o `OCR Benchmark Gate` existente. Ele não substitui a política de corpus real/anônimo (`scripts/ocr_real_corpus_policy.py`).

## Cenários

1. PDF pesquisável.
2. PDF totalmente digitalizado.
3. PDF com múltiplos documentos/imagens.
4. Documento inclinado/rotacionado.
5. Baixa resolução.
6. Foto de celular simulada.
7. Pacote sintético com CPF, RG/CIN, CNH e comprovante.
8. Página sem conteúdo útil.
9. Documento desconhecido.
10. Conteúdo ambíguo sujeito a erro de OCR.

Todos os arquivos são gerados em tempo de execução e descartados ao final do job.

## Evidências produzidas

Para cada caso, o artefato `ocr-evidence-v2.json` registra somente:

- SHA-256 do arquivo gerado;
- tipo de conteúdo;
- quantidade de páginas;
- confiança mínima e média;
- quantidade e tipos de candidatos;
- confirmação de revisão humana;
- resultado de reprocessamento idempotente;
- fingerprint SHA-256 do resultado normalizado;
- falhas do caso, quando houver.

Texto OCR bruto e identificadores pessoais não são publicados no artefato.

## Política de segurança

- `contains_personal_data=false`;
- `automatic_incorporation_allowed=false`;
- CPF/RG/CIN/CNH do cenário 7 são valores sintéticos deliberadamente inválidos;
- documento desconhecido não pode gerar candidato inesperado;
- página vazia deve falhar fechada por ausência de texto utilizável;
- nenhum candidato do gate pode dispensar revisão humana;
- corpus real continua fora do repositório e sujeito a aprovação + SHA-256 pela política existente.

## Critério de aprovação

O job `evidence-v2` aprova somente quando os 10 casos passam.

Cada caso processável é executado duas vezes sobre o mesmo arquivo. O gate exige o mesmo SHA-256 e o mesmo fingerprint lógico do resultado, cobrindo idempotência do reprocessamento.

O cenário de página vazia é aprovado apenas quando o OCR falha por ausência de texto utilizável.

## Limite atual

Este gate certifica a camada OCR e a classificação de candidatos já existente. Ele não promove automaticamente STG/PROD e não cria novos parsers de domínio para validar juridicamente CPF, RG/CIN ou CNH. A validação semântica desses documentos deve permanecer em incremento separado.
