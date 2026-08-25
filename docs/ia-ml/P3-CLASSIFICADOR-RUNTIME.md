# P3 — Classificador de requisitos: holdout, HITL, drift e rollout governado

## Objetivo

Evoluir o classificador supervisionado do P2 para um runtime governado, sem ativar automaticamente o modelo em decisões operacionais.

O P3 introduz quatro controles independentes:

1. holdout imutável e separado do treino/validação do P2;
2. amostras reais observadas com anonimização e revisão humana obrigatória;
3. monitoramento de drift de distribuição e baixa confiança;
4. rollout controlado `off -> shadow -> canary -> active`, sempre com fallback para `keyword-weighted-v1`.

## Estado inicial seguro

A política `runtime-requisitos-p3-v1` inicia com:

- `modo_padrao=off`;
- `canary_percentual=10`;
- confiança mínima do modelo `0.55`;
- mínimo de 7 amostras reais aprovadas para `canary`;
- mínimo de 14 amostras reais aprovadas para `active`;
- nenhuma promoção automática para canary/active;
- `production_touched=false`.

Enquanto o corpus observado permanecer sem revisão humana suficiente, o sistema pode no máximo operar em `shadow` por decisão explícita. O resultado funcional continua vindo do baseline P1.

## Holdout imutável

Arquivo:

`backend/data/ml/requisitos_holdout_p3_v1.jsonl`

Características:

- 28 exemplos;
- 4 exemplos para cada uma das 7 categorias;
- não participa de treino nem da validação do P2;
- versão `requisitos-holdout-p3-v1`;
- SHA-256 fixado na política;
- o CI compara o conteúdo com a base após o primeiro merge e bloqueia qualquer mutação silenciosa.

Alterar o holdout exige uma nova versão explícita de dataset/política. Não substituir o arquivo existente para melhorar artificialmente a métrica.

## Amostras reais observadas

Arquivo:

`backend/data/ml/requisitos_observados_p3_v1.jsonl`

A primeira amostra foi extraída de títulos de issues reais do próprio ReqSys. Esses registros são apenas observações de domínio e **não são ground truth**.

Cada registro possui:

- `source_ref`: referência rastreável da origem;
- `categoria_sugerida`: hipótese inicial, sem valor de aprovação;
- `anonimizado=true`;
- `revisao_status`;
- `categoria_revisada`, somente após revisão;
- `revisor_ref`, somente após revisão.

Estados permitidos:

- `PENDENTE_HUMANA` — proibido para treino e incapaz de liberar canary;
- `APROVADO` — exige categoria revisada e referência do revisor;
- `REJEITADO` — permanece como evidência, mas não entra no treino.

O loader falha fechado se detectar e-mail, CPF, CNPJ ou telefone no texto observado.

## Blueprint da revisão humana

Para cada item `PENDENTE_HUMANA`:

1. abrir a `source_ref` e verificar o contexto original;
2. confirmar que o texto sanitizado não contém PII, credencial ou dado sensível;
3. avaliar a categoria sem usar `categoria_sugerida` como prova;
4. preencher `categoria_revisada` com uma categoria válida;
5. informar `revisor_ref` rastreável, sem segredo;
6. definir `revisao_status=APROVADO` ou `REJEITADO`;
7. executar o P3 Gate;
8. anexar a execução como evidência antes de qualquer mudança de modo.

Critério de conclusão da revisão: nenhum item aprovado sem categoria revisada/revisor e nenhuma amostra sensível versionada.

## Modos de runtime

### `off`

- baseline P1 responde;
- modelo supervisionado não influencia a decisão;
- modo padrão.

### `shadow`

- baseline P1 continua respondendo;
- P2 calcula classificação paralela apenas para telemetria/comparação;
- divergências podem alimentar métricas de drift;
- sem impacto funcional.

### `canary`

- exige no mínimo 7 amostras reais aprovadas;
- seleção determinística por SHA-256 do `correlation_id`;
- padrão inicial: 10% das correlações;
- baixa confiança retorna automaticamente ao baseline;
- ausência do gate humano retorna `REAL_SAMPLE_GATE_BLOCKED`.

### `active`

- exige no mínimo 14 amostras reais aprovadas;
- ainda respeita confiança mínima e fallback para baseline;
- não deve ser habilitado apenas por alteração de variável sem evidência do gate e avaliação de drift.

## Drift

O P3 mede:

- distribuição observada das sete categorias;
- Jensen-Shannon divergence contra a distribuição de referência;
- taxa de classificações abaixo da confiança mínima;
- delta por categoria.

Alertas iniciais:

- `CATEGORY_DISTRIBUTION_DRIFT` quando JS divergence >= `0.15`;
- `LOW_CONFIDENCE_RATE` quando taxa de baixa confiança >= `0.25`.

Um alerta deve impedir avanço de rollout até revisão da causa. Não ajustar o limiar apenas para remover o alerta.

## Fail-safe

Em erro do modelo, confiança insuficiente, canary não selecionado ou gate humano incompleto, a resposta retorna ao baseline `keyword-weighted-v1`.

O `correlation_id` é obrigatório para o runtime governado e é a chave determinística do canary.

## Evidência CI

Workflow:

`.github/workflows/ml-requirement-classifier-p3-gate.yml`

O gate valida:

- imutabilidade do holdout;
- testes P1/P2/P3;
- política de PII e revisão humana;
- qualidade no holdout;
- smoke de drift;
- prontidão máxima permitida pelo número de amostras humanas aprovadas;
- artifact `ml-requirement-classifier-p3-evidence`.

Estados de prontidão possíveis:

- `BLOQUEADO_QUALIDADE`;
- `APROVADO_PARA_SHADOW`;
- `APROVADO_PARA_CANARY`;
- `APROVADO_PARA_ACTIVE`.

O estado de prontidão é evidência de engenharia; não executa deploy nem altera automaticamente o modo do runtime.
