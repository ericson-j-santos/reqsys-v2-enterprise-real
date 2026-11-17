# Correção de pré-requisitos CI hospedado — ReqSys #3138 / PR #3141

## Contexto reproduzido
No SHA `d2fecddd0e4ff3fff4596f11dc7cdd0b7a479aee`, os workflows GitHub Actions `CI — ReqSys v2 Enterprise` run #43050487916 e `Golden Test Advanced` run #43050487947 falharam antes dos testes por dependência apt e falha de DNS para `azure.archive.ubuntu.com`. PR Evidence e Governed Merge Queue falharam em decorrência; não dispensar estes gates.

## Requisitos
1. Preservar todos os testes e patamares atuais de backend e frontend; nunca transformar `failure` em `skipped` ou `success` artificial.
2. Para `pyodbc==5.2.0` já fixado no backend, usar distribuição binária somente, validar importação e API `drivers()` do gerenciador ODBC; se wheel ou biblioteca faltarem, falhar.
3. Para Playwright, usar o Chrome pré-instalado oficialmente no GitHub-hosted Ubuntu, com verificação explícita do binário e versão; se faltar, falhar.
4. O Playwright local continua utilizando sua configuração normal de Chromium, sem dependência de variável de CI.
5. Restringir alterações a CI, configuração de Playwright, testes de contrato e SDD; nenhuma alteração no Gateway, hosts, labels, secrets, Docker, ambiente ou deploy.

## Critérios de aceite
- Os três arquivos modificados possuem sintaxe válida em YAML/JavaScript, com testes positivos e negativos de contrato.
- O job backend executa o teste real de importação do `pyodbc`, mantendo testes e cobertura obrigatórios.
- O job visual valida presença e versão do Chrome antes de executar o teste de acessibilidade real.
- Falhas de instalação/ausência de binário continuam bloqueando o pipeline.
- `scripts/sdd_gate.py` aceita o manifesto SDD e teste mapeado; novo Pre-PR e CI devem ser avaliados no SHA resultante.
- Se rede PyPI continuar indisponível ou o wheel não for suficiente, registrar falha real e não dispensar dependência.
- O E2E físico de #3138 continua não executado e não é autorizado por este reparo de CI.

## Risco e rollback
O Chrome do runner pode diferir da revisão de Chromium embarcada pelo Playwright. Os testes reais e regressões do próprio workflow permanecem obrigatórios. Reverter somente estas alterações em PR após revisão, sem rebaixar gates.

- O contrato legado `tests/test_native_postgres_ci_contract.py` também deve exigir a versão binária, a importação de pyodbc e a chamada real do gerenciador; testes negativos rejeitam a remoção de cada verificação. Esse ajuste é reparo do teste da própria dependência alterada, não redução de cobertura.
