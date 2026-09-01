# OCR Real Corpus Certification v1

## Objetivo

Certificar o OCR do ReqSys contra documentos reais previamente anonimizados ou homologados, mantendo todo o conteúdo documental fora do repositório e fora dos artefatos do GitHub Actions.

O fluxo é fail-closed: ausência de aprovação, hash divergente, dado pessoal declarado, revisão humana ausente ou métrica abaixo do limite impede promoção.

## Fluxo governado

1. Preparar documentos reais em diretório controlado fora do repositório.
2. Anonimizar/homologar cada documento antes de qualquer execução.
3. Criar manifesto externo com SHA-256, tipo documental, texto esperado e referência de revisão humana.
4. Validar o manifesto com `scripts/ocr_real_corpus_policy.py`.
5. Executar o OCR com o mesmo `TesseractDocumento` usado pela aplicação.
6. Comparar resultado OCR com a verdade conhecida por CER e Exact Match.
7. Produzir evidência sanitizada sem texto OCR bruto.
8. Tornar DEV→STG elegível somente quando todos os critérios forem atendidos.

## Manifesto externo

Exemplo estrutural, sem dados reais:

```json
{
  "schema_version": "1.0.0",
  "approval_reference": "HAB-OCR-APPROVAL-001",
  "contains_personal_data": false,
  "max_average_cer": 0.10,
  "min_exact_match": 0.80,
  "cases": [
    {
      "case_id": "cpf-001",
      "document_type": "CPF",
      "file": "cpf/caso-001.png",
      "sha256": "<64 hex>",
      "classification": "ANONYMIZED_APPROVED",
      "contains_personal_data": false,
      "expected": "<verdade conhecida anonimizada>",
      "human_review_reference": "REV-001",
      "max_cer": 0.10
    }
  ]
}
```

O manifesto também deve permanecer fora do repositório porque o campo `expected` pode representar conteúdo derivado do documento.

## Critérios de certificação

Por caso:

- classificação `ANONYMIZED_APPROVED` ou `HOMOLOGATED_APPROVED`;
- `contains_personal_data=false`;
- SHA-256 íntegro;
- referência de revisão humana presente;
- CER menor ou igual ao limite do caso, padrão 10%.

No corpus:

- 100% dos casos devem passar;
- CER médio máximo padrão de 10%;
- Exact Match mínimo padrão de 80%;
- nenhuma revisão humana pendente.

Os limites podem ser endurecidos no manifesto, mas não devem ser relaxados sem decisão de governança documentada.

## Evidência publicada

O arquivo `ocr-real-corpus-certification.json` contém somente:

- IDs dos casos;
- tipo documental;
- SHA-256;
- quantidade de páginas;
- confiança média;
- CER;
- indicador Exact Match;
- presença de referência de revisão humana;
- métricas agregadas por tipo;
- estado `PASS`, `FAIL` ou `BLOCKED`;
- elegibilidade de promoção.

Texto OCR bruto e texto esperado não são publicados.

## Execução

A política atual do ReqSys não autoriza runners self-hosted. Por isso, o GitHub Actions valida apenas o contrato, a sintaxe e os testes do certificador em runner hospedado pelo GitHub. A execução com corpus real acontece fora do GitHub Actions, em ambiente controlado que tenha acesso local ao corpus externo.

```bash
python scripts/ocr_real_corpus_certify.py \
  --manifest /secure/ocr/manifest.json \
  --corpus-root /secure/ocr/corpus \
  --output artifacts/ocr-real-corpus-certification.json
```

O resultado sanitizado pode ser anexado posteriormente à trilha de evidências de release, sem incluir corpus, texto OCR bruto ou verdade conhecida.

## Critério DEV → STG

`promotion_eligible=true` é evidência necessária, mas não executa promoção automaticamente. A promoção continua sujeita aos demais gates de release do ReqSys.

## Bloqueio humano explícito

A primeira certificação real depende de duas ações que não podem ser fabricadas pelo CI:

1. disponibilizar corpus real anonimizado/homologado em armazenamento controlado;
2. registrar aprovação e revisão humana de cada caso no manifesto externo.

Sem essas evidências o gate deve permanecer bloqueado.
