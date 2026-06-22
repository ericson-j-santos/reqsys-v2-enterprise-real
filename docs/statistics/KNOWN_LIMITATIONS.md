# Limitações Conhecidas — Aba Estatísticas v1

## Limitações atuais

- Os indicadores internos iniciais ainda usam fonte local no frontend.
- A fonte externa inicial é propositalmente `nao_medido`.
- Não há endpoint backend dedicado `/api/estatisticas` nesta versão.
- Não há integração real ainda com GitHub Actions, PRs ou runtime.
- A execução de testes/build depende do CI após abertura do PR.

## Por que essas limitações são aceitáveis neste incremento

O objetivo da v1 é criar a estrutura navegável, contrato, guard rails e governança visual. A conexão com dados reais deve ocorrer no próximo incremento sem quebrar o contrato já criado.

## Critério para remover limitações

- Implementar endpoint backend real.
- Criar registry de fontes externas autorizadas.
- Conectar dados internos reais.
- Adicionar E2E responsivo.
- Validar CI verde antes de revisão final.
