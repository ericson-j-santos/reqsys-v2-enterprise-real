# Aceite de risco — Autonomous Delivery Cycle

## Risco aceito nesta versão

Aceita-se ativar automação conservadora de merge desde que:

- o PR possua autorização explícita por label;
- a fila governada tenha marcado elegibilidade;
- todos os workflows obrigatórios estejam verdes;
- o merge use SHA esperado;
- o ciclo publique evidência auditável.

## Risco não aceito

- Merge sem label explícita.
- Merge com workflow obrigatório pendente ou vermelho.
- Merge sem observação pós-merge.
- Execução automática de próximo incremento.

## Responsável operacional

Governança do repositório ReqSys.
