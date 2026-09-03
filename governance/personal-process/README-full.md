# Personal Process Control v1

Controle de processos pessoais/profissionais executado na infraestrutura do ReqSys, mas isolado do dominio funcional do produto.

## Uso

1. Registre ou atualize demandas em `demandas.json`.
2. Todo item aberto deve conter `proxima_acao`.
3. Item `Concluido` exige `criterio_conclusao` e `evidencia`.
4. Item `Bloqueado` exige `tipo_bloqueio` diferente de `Nenhum`.
5. Registre componentes reutilizaveis em `biblioteca.json`.
6. Registre tarefas manuais candidatas a automacao em `automacoes.json`.

Execucao local:

```bash
python scripts/personal_process_control.py --as-of 2026-09-03
```

Saidas em `artifacts/personal-process/`:

- `snapshot.json`: estado validado e indicadores;
- `pareto.json`: priorizacao de demandas e automacoes;
- `relatorio.md`: resumo diario ou semanal aprofundado;
- `controle_mestre_processos.xlsx`: visao portatil para consulta.

## Cadencia

O workflow executa diariamente. Nas segundas-feiras, o programa muda automaticamente para `semanal_aprofundado`, acrescentando revisao de causas recorrentes, automacao e reuso.

## Falha fechada

Dados invalidos interrompem a execucao antes da geracao dos artefatos. O sistema nao considera um item concluido sem evidencia objetiva.
