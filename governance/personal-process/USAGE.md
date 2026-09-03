# Uso do Personal Process Control v1

## Fluxo diário

1. Atualize `demandas.json` com novas demandas ou mudanças de estado.
2. Atualize `biblioteca.json` quando uma solução recorrente virar componente reutilizável.
3. Atualize `automacoes.json` quando uma tarefa manual recorrente for identificada.
4. O workflow diário valida governança, calcula Pareto e gera os artefatos.
5. Use `relatorio.md` para decisão rápida e `controle_mestre_processos.xlsx` para consulta portátil.

## Regras bloqueantes

- item aberto sem `proxima_acao`: falha;
- item `Concluido` sem `criterio_conclusao`: falha;
- item `Concluido` sem `evidencia`: falha;
- item `Bloqueado` sem `tipo_bloqueio`: falha;
- IDs duplicados: falha;
- pontuações fora de 1 a 5: falha.

## Cadência

O workflow executa todos os dias às 11:07 UTC, equivalente a 08:07 no horário de Brasília. Às segundas-feiras, o relatório entra automaticamente no modo `semanal_aprofundado`.

## Execução local

```bash
python -m unittest discover -s tests -p 'test_personal_process_control.py' -v
python scripts/personal_process_control.py --as-of 2026-09-03
```

## Artefatos

- `snapshot.json`: estado consolidado e hashes SHA-256 das entradas;
- `pareto.json`: ordenação e faixa Pareto;
- `relatorio.md`: decisão operacional diária/semanal;
- `controle_mestre_processos.xlsx`: visão portátil determinística.
