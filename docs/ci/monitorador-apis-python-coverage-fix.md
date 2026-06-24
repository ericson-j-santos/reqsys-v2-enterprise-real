# Correção CI — Monitorador de APIs Python

## Contexto

Após o merge do PR #161, o workflow `Testes Monitorador APIs Python` falhou na etapa `Executar testes com cobertura mínima`.

## Evidência

- Workflow: `Testes Monitorador APIs Python`
- Run: `28068262472`
- Job: `83097214550`
- Etapa com falha: `Executar testes com cobertura mínima`
- Gate configurado: `pytest --cov=app --cov-report=term-missing --cov-fail-under=85`

## Causa provável

A suíte `tests/test_api.py` cobria apenas endpoints básicos (`/health`, `/`, `/api/resultados`) e não exercitava caminhos relevantes dos endpoints assíncronos `/api/monitorar` e `/dashboard`, reduzindo a cobertura global do pacote `app`.

## Correção aplicada

- Expansão de `examples/monitorador_apis_python/tests/test_api.py`.
- Inclusão de testes para normalização de limite mínimo e máximo em `/api/resultados`.
- Inclusão de teste mockado para `/api/monitorar` sem chamada externa real.
- Inclusão de teste mockado para `/dashboard` sem dependência de rede ou persistência externa.

## Decisão de governança

A correção preserva o gate de cobertura mínima em 85%.

Não foi reduzido o limiar de qualidade do workflow.

## Limites

- Não altera runtime de produção.
- Não altera deploy.
- Não executa chamadas externas reais nos testes.
- Não altera o workflow, exceto se validação posterior indicar necessidade.
