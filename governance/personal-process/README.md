# Personal Process Control v1.1

Controle de processos pessoais/profissionais executado na infraestrutura do ReqSys, mas isolado do domínio funcional do produto.

## Evolução v1.1

- substitui a carga demonstrativa por processos reais fora do ReqSys;
- exige `origem` e `estado_evidenciado_em` por demanda;
- acumula `historico.json` diariamente, com substituição idempotente do mesmo dia;
- restaura o histórico do último artefato bem-sucedido sem escrita automática na `main`;
- adiciona aba `Historico` ao XLSX;
- mantém revisão diária e modo semanal aprofundado às segundas-feiras.

## Uso

Atualize `demandas.json` somente com estado evidenciado. Item aberto exige `proxima_acao`; concluído exige critério e evidência; bloqueado exige classificação do bloqueio.

Execução local:

```bash
python -m unittest discover -s tests -p 'test_personal_process_control.py' -v
python scripts/personal_process_control.py --as-of 2026-09-04
```

Com histórico anterior:

```bash
python scripts/personal_process_control.py --history-input artifacts/previous/historico.json --as-of 2026-09-04
```

## Artefatos

- `snapshot.json`
- `pareto.json`
- `historico.json`
- `relatorio.md`
- `controle_mestre_processos.xlsx`
