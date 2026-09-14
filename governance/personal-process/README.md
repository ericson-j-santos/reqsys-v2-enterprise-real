# Personal Process Control v1.2

Controle contínuo de pendências pessoais/profissionais executado na infraestrutura do ReqSys, isolado do domínio funcional do produto.

## Evolução v1.2

- transforma o levantamento em fila governada até estado terminal verificável;
- adota os estados `Detectada`, `Triada`, `Pronta para execucao`, `Em execucao`, `Aguardando evidencia`, `Bloqueada externamente`, `Concluido`, `Cancelado` e `Duplicada`;
- limita o trabalho em andamento a no máximo três itens nos estados `Em execucao` e `Aguardando evidencia`;
- calcula aging pela `ultima_movimentacao_em` e sinaliza atenção, escalonamento e criticidade;
- prioriza pelo maior retorno operacional usando impacto, desbloqueio, urgência e esforço;
- valida dependências e marca duplicidades de forma explícita;
- exige responsável para bloqueios externos;
- transforma pendência aberta por três ciclos de histórico em candidato explícito à automação, exceto bloqueios externos;
- preserva histórico diário idempotente e o modo semanal aprofundado.

## Prioridade operacional

A fila usa a fórmula:

`impacto × fator_desbloqueio × fator_urgencia ÷ esforco`

- `impacto`: nota de 1 a 5;
- `fator_desbloqueio`: 1 + quantidade de itens abertos que dependem da pendência, limitado a 5;
- `fator_urgencia`: maior valor entre a frequência cadastrada e a urgência derivada do aging;
- `esforco`: nota de 1 a 5.

Faixas: `P0 >= 40`, `P1 >= 15`, `P2 >= 5`, `P3 < 5`.

## Aging

- até 7 dias: `normal`;
- 8 a 14 dias: `atencao`;
- 15 a 30 dias: `escalar`;
- acima de 30 dias: `critico`.

## Regras de encerramento

- `Concluido`: exige `criterio_conclusao` e `evidencia`;
- `Cancelado`: estado terminal explícito;
- `Duplicada`: exige `duplicado_de` apontando para outro item existente;
- `Bloqueada externamente`: exige tipo de bloqueio, responsável e próxima ação;
- qualquer item aberto exige próxima ação e critério de conclusão.

## Uso

Atualize `demandas.json` somente com estado evidenciado, registrando também `ultima_movimentacao_em`, dependências e causa raiz quando conhecida.

Execução local:

```bash
python -m unittest discover -s tests -p 'test_personal_process_control.py' -v
python scripts/personal_process_control.py --as-of 2026-09-14
```

Com histórico anterior:

```bash
python scripts/personal_process_control.py --history-input artifacts/previous/historico.json --as-of 2026-09-14
```

## Artefatos

- `snapshot.json`: estado consolidado, WIP, aging, causas raiz e próximo incremento;
- `pareto.json`: fila priorizada e candidatos de automação;
- `historico.json`: histórico diário idempotente;
- `relatorio.md`: visão operacional e próxima ação executável;
- `controle_mestre_processos.xlsx`: visão portátil determinística.

O workflow `Personal Process Control Daily` continua sendo o executor diário e restaura o último histórico bem-sucedido antes de gerar o novo ciclo.
