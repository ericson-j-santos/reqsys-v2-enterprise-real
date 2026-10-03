# Análise governada de documentos para construção de demanda

## Objetivo

Permitir que arquivos enviados ao ReqSys sejam analisados como fontes de informação para uma demanda sem alterar automaticamente requisitos existentes.

## Escopo inicial

- Ambiente alvo: DEV.
- Produção não deve ser alterada por este incremento.
- Tipos priorizados: PDF, imagem, DOCX, XLSX/CSV, TXT e JSON.
- PDFs/imagens podem usar o bounded context `ocr_evidencia` quando aplicável.
- Toda informação extraída é tratada como candidata até decisão humana explícita.

## Fluxo

1. Receber arquivo e metadados da demanda.
2. Validar tipo, tamanho, integridade e nome seguro.
3. Calcular SHA-256 do arquivo para idempotência e rastreabilidade.
4. Extrair conteúdo textual nativo quando disponível.
5. Para PDF/imagem sem texto suficiente, encaminhar para `ocr_evidencia`.
6. Classificar trechos extraídos em categorias de engenharia de requisitos.
7. Detectar conflitos com requisitos existentes.
8. Marcar conteúdo incerto como hipótese.
9. Exigir revisão humana antes de incorporar qualquer item na demanda.
10. Registrar origem, página/trecho, decisão, usuário responsável e correlation_id.

## Classificações mínimas

- requisito_funcional
- requisito_nao_funcional
- regra_negocio
- restricao
- dado_referencia
- contexto
- conflito
- hipotese
- ignorar

## Estados do item candidato

- EXTRAIDO
- CLASSIFICADO
- PENDENTE_REVISAO
- APROVADO
- REJEITADO
- INCORPORADO

Transições inválidas devem falhar de forma fechada.

## Contrato lógico do item candidato

```json
{
  "id": "uuid",
  "demanda_id": "string",
  "arquivo_sha256": "hex",
  "arquivo_nome": "string",
  "pagina": 14,
  "trecho": "Sistema deve validar CPF",
  "classificacao": "regra_negocio",
  "confianca": 0.93,
  "estado": "PENDENTE_REVISAO",
  "conflitos": [],
  "correlation_id": "uuid",
  "criado_em": "ISO-8601"
}
```

## Regras obrigatórias

- Nenhum item pode ser incorporado automaticamente.
- A decisão humana deve ser auditável.
- O hash do arquivo deve permitir deduplicação/idempotência.
- Conteúdo sensível deve seguir mascaramento e política LGPD vigente do ReqSys.
- Falha de OCR não deve resultar em aprovação implícita.
- Conflitos precisam permanecer visíveis até decisão.
- A origem do requisito deve permanecer rastreável até o arquivo e trecho de origem.

## Critério de pronto para o próximo incremento

- Contrato persistente dos itens candidatos definido.
- Endpoint DEV de upload/análise implementado.
- Integração com `ocr_evidencia` por adaptador.
- Testes de segurança, idempotência, transição de estados e falha fechada verdes.
- CI verde na branch/PR antes de qualquer promoção.
