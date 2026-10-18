# Diagnóstico mascarado do Gitleaks no GitLab

## Problema e fonte
A pipeline GitLab 2960098236, no SHA d1db91274de744aeee17da029e908f4486bfc31a,
falhou no job 17264155071 com cinco achados. O log informa apenas a contagem;
o relatório JSON existe, mas o conector usado nesta continuação não oferece
download de artifacts GitLab. Isso impede a triagem pela interface de logs
sem uma alteração diagnóstica. Não há classificação de falso positivo.

## Incremento
Acrescentar --verbose e --no-color e explicitar --redact=100 na mesma chamada
Gitleaks já existente. Preservar imagem/digest, --source ., --no-git,
.gitleaks.toml, relatório JSON e --exit-code 1. Nenhuma exceção, exclusão de
caminho, segredo, permissão, deploy ou novo workflow é acrescentado.

## Critérios de aceite
- O contrato da configuração passa e detecta o comando anterior sem diagnóstico.
- Controles negativos recusam mascaramento parcial, alteração de escopo,
  ausência de política, exit code zero e supressão por || true.
- Validação repetida não muda os dados de entrada.
- Pre-PR Readiness executa os testes no HEAD exato.
- Após integração autorizada e mirror, o job GitLab real apresenta achados
  mascarados e mantém falha quando existem achados.
- Essa melhoria NÃO resolve nem homologa os cinco achados. A correção de cada
  causa deve usar a triagem do relatório/log, sem allowlist ampla.

## Referência da interface
https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md

## Reversão
Reverter somente o incremento diagnóstico, preservando o scanner e sua política.
