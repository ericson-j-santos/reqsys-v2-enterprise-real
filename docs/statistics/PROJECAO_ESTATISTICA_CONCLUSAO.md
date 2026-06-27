# ReqSys — Projecao Estatistica de Conclusao

## Objetivo

Consolidar em um unico payload da API de estatisticas uma leitura executiva de conclusao baseada em ritmo recente de PRs/merges, estabilizacao de CI, maturidade atual e gap remanescente.

## Endpoint

`GET /v1/estatisticas` passa a incluir o bloco `projecaoConclusao` em `data`.

## Estrutura principal

- `referenciaTemporal`: timestamp de referencia da analise.
- `estadoAtualConsolidado`: maturidade atual por dimensao.
- `velocidadeAtualObservada`: cadencia operacional recente.
- `percentualRealConclusao`: percentual real por eixo de consolidacao.
- `gapsRestantes`: gap por area prioritaria.
- `cenarios.conservador` e `cenarios.acelerado`: throughput e marcos com faixa de dias.
- `gargalosPrincipais`, `riscos`, `tendencias`: leitura tatico-estrategica.
- `probabilidades`: probabilidade de atingimento por resultado.
- `aceleradoresMarginais`: alavancas de maior ganho marginal.
- `leituraExecutiva`: estado atual, fortalezas e focos restantes.

## Metodo de projecao

1. O `completionScore` e a media dos indicadores de conclusao.
2. O `throughputScore` usa a media de merges verdes por dia util normalizada.
3. Cada cenario define uma faixa de throughput (`pontos/dia`).
4. Cada marco usa uma carga de esforco em pontos.
5. A faixa de dias por marco e calculada por:
   - `minDias = round(esforcoPontos / throughputMax)`
   - `maxDias = round(esforcoPontos / throughputMin)`
6. As probabilidades aplicam ponderacao de:
   - score de conclusao;
   - estabilizacao de CI;
   - throughput observado;
   - bonus de tendencia;
   - penalidade de risco por resultado.

## Guard rails

- Modelo heuristico report-only (nao dispara automacoes).
- Nao altera estado de ambientes, CI, deploy ou governanca.
- Nao mascara o que esta pendente: gaps, riscos e gargalos permanecem explicitos.
