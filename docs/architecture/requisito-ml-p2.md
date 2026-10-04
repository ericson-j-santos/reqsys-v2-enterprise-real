# Classificador supervisionado de requisitos — P2

## Objetivo

Substituir a validação exclusivamente heurística do P1 por um modelo supervisionado reproduzível, mantendo o classificador `keyword-weighted-v1` como baseline comparável e auditável.

## Implementação

- Modelo: `multinomial-nb-word-char-ngram-v1`.
- Algoritmo: Multinomial Naive Bayes com suavização de Laplace (`alpha=1.0`).
- Features: unigramas, bigramas e n-grams de caracteres de tamanho 3, 4 e 5.
- Dependências de runtime: somente Python stdlib.
- Dataset: `backend/data/ml/requisitos_classificador_v1.jsonl`.
- Política: `backend/data/ml/politica_promocao_requisitos_v1.json`.
- Evidência: `artifacts/ml-requirement-classifier/metrics.json` e `model.json` no CI.

## Dataset v1

O dataset contém 84 exemplos rotulados e balanceados entre as sete categorias do P1:

- 56 exemplos de treino, 8 por categoria;
- 28 exemplos de validação, 4 por categoria.

A origem `curated_internal_p2` indica que os exemplos foram curados para o contrato do P2. Este conjunto não deve ser tratado como evidência de generalização sobre tráfego real de produção.

## Gate de promoção

A promoção fica bloqueada se qualquer condição falhar:

1. `macro_f1(modelo) >= 0.78`;
2. `macro_f1(modelo) - macro_f1(baseline) >= 0.05`;
3. `macro_f1(modelo) > macro_f1(baseline)`;
4. dataset/política/modelo precisam possuir versões compatíveis;
5. cada categoria precisa atender ao suporte mínimo de treino e validação.

O CLI retorna código `2` quando as métricas não permitem promoção e código `3` quando dataset, política ou treinamento estão inválidos. Ambos os casos são fail-closed.

## Execução local

```bash
python scripts/avaliar_classificador_requisitos_ml.py
```

Para executar apenas os testes do contrato:

```bash
cd backend
PYTHONPATH=. pytest -q tests/test_requisito_classifier.py tests/test_requisito_ml.py
```

## Limitação conhecida

O P2 valida capacidade técnica e governança do treinamento supervisionado, mas ainda usa corpus curado. Antes de habilitar o modelo como classificador padrão em produção, o próximo incremento deve incorporar amostras reais anonimizadas e revisadas, separar teste final imutável e adicionar monitoramento de drift por categoria.
