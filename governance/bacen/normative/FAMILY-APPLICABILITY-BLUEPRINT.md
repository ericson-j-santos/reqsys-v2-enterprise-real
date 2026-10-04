# Blueprint — decisão institucional de aplicabilidade CMN-4893

## Objetivo

Formalizar a decisão institucional que determina se a família regulatória `CMN-4893` é aplicável ao escopo avaliado pelo ReqSys.

O ReqSys **não decide automaticamente** se a instituição é ou não abrangida pela norma. Ele valida, registra e aplica uma decisão institucional já tomada por autoridade competente.

## Pré-requisitos

1. Identificar a pessoa ou função institucional com autoridade para decidir o enquadramento regulatório.
2. Identificar a entidade jurídica e o tipo institucional avaliados.
3. Registrar a justificativa e a referência da aprovação institucional.
4. Decidir apenas entre:
   - `applicable`
   - `not_applicable`

Ausência de informação mantém `pending_decision`.

## Arquivo a preencher

`governance/bacen/normative/FAMILY-APPLICABILITY-DECISION.yaml`

Para uma decisão final, preencher obrigatoriamente:

- `decision`
- `decided_by`
- `decided_at` em UTC
- `rationale`
- `approval_reference`
- `institutional_scope.legal_entity`
- `institutional_scope.entity_type`

Os campos de RSFN, Pix, STR e SMF devem refletir o conhecimento institucional disponível. Se ainda não houver decisão sobre um deles, manter `unknown`; isso não converte requisito condicional em não aplicável.

## Evidência esperada

O commit/PR da decisão deve apontar para uma referência institucional rastreável em `approval_reference`, por exemplo identificador de ata, parecer, decisão GRC ou sistema oficial. O repositório não deve armazenar conteúdo sensível quando a referência puder apontar para o repositório institucional de origem.

## Validação automática

Executar:

```bash
python scripts/validate_bacen_family_applicability.py \
  --decision-file governance/bacen/normative/FAMILY-APPLICABILITY-DECISION.yaml
```

Resultado esperado para decisão final válida:

- `result: valid`
- `decision_is_final: true`
- `human_authority_required: true`
- `automatic_inference_allowed: false`

## Critério de conclusão

A ação humana está concluída quando:

1. o registro possui decisão final válida;
2. o responsável, data, justificativa e referência de aprovação estão preenchidos;
3. o Gate 2 lê o registro autoritativo;
4. os gates da PR ficam verdes;
5. a decisão é mergeada na `main`.

Depois disso, se a família for `applicable`, o Gate 2 passa a derivar o estado das 57 obrigações e exige que requisitos condicionais sejam avaliados ou formalmente marcados como não aplicáveis por obrigação. Se a família for `not_applicable`, a mesma trilha formal de autoridade continua obrigatória.
