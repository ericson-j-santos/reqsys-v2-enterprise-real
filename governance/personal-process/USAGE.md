# Uso do Personal Process Control v1.2

## Fluxo diário

1. Atualize `demandas.json` somente com estado verificável.
2. Registre `ultima_movimentacao_em` quando houver mudança material de estado, evidência, bloqueio ou próxima ação.
3. Registre `dependencias` por ID quando um item depender de outro.
4. Use `Bloqueada externamente` somente quando a continuidade depender de ação fora do executor atual; informe `tipo_bloqueio` e `responsavel_bloqueio`.
5. Use `Duplicada` somente com `duplicado_de` apontando para o item canônico.
6. Atualize `biblioteca.json` quando uma solução recorrente virar padrão reutilizável.
7. Atualize `automacoes.json` quando uma tarefa manual recorrente for identificada.
8. O workflow diário valida governança, WIP, aging, dependências, Pareto e recorrência, e gera os artefatos.

## Estados

Fluxo principal:

`Detectada -> Triada -> Pronta para execucao -> Em execucao -> Aguardando evidencia -> Concluido`

Estados terminais/paralelos:

- `Bloqueada externamente`;
- `Cancelado`;
- `Duplicada`.

Um item não deve ser considerado concluído apenas porque houve implementação, execução ou retorno HTTP positivo. `Concluido` exige critério de conclusão e evidência.

## Regras bloqueantes

- item aberto sem `proxima_acao`: falha;
- item aberto sem `criterio_conclusao`: falha;
- item `Concluido` sem evidência: falha;
- item `Bloqueada externamente` sem responsável ou tipo de bloqueio: falha;
- dependência inexistente, duplicada ou autorreferente: falha;
- item `Duplicada` sem alvo válido: falha;
- mais de três itens em `Em execucao` + `Aguardando evidencia`: falha;
- datas fora de `YYYY-MM-DD`: falha;
- IDs duplicados ou pontuações fora de 1 a 5: falha.

## Aging e escalonamento

- até 7 dias sem movimentação: normal;
- 8 a 14 dias: atenção;
- 15 a 30 dias: escalar;
- acima de 30 dias: crítico.

O aging aumenta a urgência usada na priorização. Uma pendência aberta presente em pelo menos três ciclos de histórico vira candidato à automação quando não estiver bloqueada externamente.

## WIP e próxima ação

O limite é de três itens ativos. Enquanto houver capacidade, o próximo incremento é o item executável de maior índice operacional. Ao atingir o limite, o controle deixa de puxar novos itens e recomenda concluir um item já ativo.

## Cadência

O workflow executa todos os dias às 11:07 UTC, equivalente a 08:07 no horário de Brasília. Às segundas-feiras, o relatório entra automaticamente no modo `semanal_aprofundado`.

## Execução local

```bash
python -m unittest discover -s tests -p 'test_personal_process_control.py' -v
python scripts/personal_process_control.py --as-of 2026-09-14
```

## Artefatos

- `snapshot.json`: estado consolidado, governança, WIP e aging;
- `pareto.json`: fila priorizada e recorrências;
- `historico.json`: continuidade idempotente por data;
- `relatorio.md`: decisão operacional e próximo incremento;
- `controle_mestre_processos.xlsx`: visão portátil determinística.
