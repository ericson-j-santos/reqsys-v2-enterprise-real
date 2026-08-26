# P3 — Classificador de requisitos: holdout, HITL, drift e rollout governado

## Objetivo

Evoluir o classificador supervisionado do P2 para um runtime governado, sem ativar automaticamente o modelo em decisões operacionais.

O P3 introduz quatro controles independentes:

1. holdout imutável e separado do treino/validação do P2;
2. amostras reais observadas com anonimização e revisão humana obrigatória;
3. monitoramento de drift de distribuição e baixa confiança;
4. rollout controlado `off -> shadow -> canary -> active`, sempre com fallback para `keyword-weighted-v1`.

## Estado inicial seguro

A política `runtime-requisitos-p3-v1.1` mantém:

- `modo_padrao=off`;
- `canary_percentual=10`;
- `active_habilitado=false`;
- confiança mínima do modelo `0.55`;
- mínimo de 7 amostras reais aprovadas para `canary`;
- mínimo de 14 amostras reais aprovadas para `active`;
- mínimo de 1 amostra real aprovada em cada uma das 7 categorias para `active`;
- nenhuma promoção automática para canary/active;
- `production_touched=false`.

Após a revisão humana registrada na issue #1323, o corpus possui 16 amostras atômicas aprovadas, 1 registro não atômico rejeitado e cobertura das 7 categorias. Isso permite ao gate declarar prontidão para `canary`, mas não ativa esse modo: o adaptador da API continua aceitando somente `off` e `shadow`, e o resultado funcional continua vindo do baseline P1.

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

As amostras foram extraídas de issues reais do próprio ReqSys. `categoria_sugerida` é somente uma hipótese; apenas `categoria_revisada` com `revisor_ref` rastreável constitui decisão humana aceita pelo gate.

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
- `REJEITADO` — exige referência humana, permanece como evidência e não entra no treino.

O loader falha fechado se detectar e-mail, CPF, CNPJ ou telefone no texto observado.
Somente registros `APROVADO` são incorporados ao treino do runtime; pendências e rejeições ficam fora do modelo.

### Revisão da issue #1323

- 13 registros originais aprovados;
- 3 recategorizações humanas: issues #1103, #729 e #958;
- registro original da issue #1288 rejeitado por não atomicidade e dividido em duas amostras (`SEGURANCA` e `DADOS`);
- 1 amostra `FUNCIONAL` adicionada a partir da issue #1115;
- total versionado: 17 registros, sendo 16 aprovados e 1 rejeitado.

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
- a prontidão do CI não conecta nem habilita canary na API;
- o primeiro canary real deve ser integrado somente em DEV, com contagem derivada do corpus validado e telemetria de eventos reais.

### `active`

- exige no mínimo 14 amostras reais aprovadas;
- exige cobertura mínima das sete categorias;
- exige `active_habilitado=true`, atualmente fixado em `false`;
- ainda respeita confiança mínima e fallback para baseline;
- deve permanecer bloqueado até existir evidência de shadow/canary sobre eventos reais;
- quando autorizado em ciclo posterior, deve ser exercitado somente em STG; produção permanece `off` e deve falhar fechada para qualquer outro modo.

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

O relatório do gate calcula um smoke de drift sobre o holdout controlado. Esse valor não representa tráfego real e, sozinho, nunca habilita `active`. Divergência e baixa confiança reais precisam ser medidas em DEV antes de qualquer promoção posterior.

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
- prontidão permitida pela qualidade, revisão humana, cobertura por categoria e trava explícita de `active`;
- artifact `ml-requirement-classifier-p3-evidence`.

Estados de prontidão possíveis:

- `BLOQUEADO_QUALIDADE`;
- `APROVADO_PARA_SHADOW`;
- `APROVADO_PARA_CANARY`;
- `APROVADO_PARA_ACTIVE`.

O estado de prontidão é evidência de engenharia; não executa deploy nem altera automaticamente o modo do runtime.
Com `active_habilitado=false`, o máximo esperado após a revisão da #1323 é `APROVADO_PARA_CANARY`.
