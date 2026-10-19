# Diagnóstico e remediação dos achados Gitleaks no GitLab

## Problema e evidência real
A pipeline GitLab 2960098236, no SHA d1db91274de744aeee17da029e908f4486bfc31a,
falhou no job 17264155071 com cinco achados. O incremento diagnóstico foi
reproduzido de forma byte a byte em uma branch GitLab temporária, a partir da
mesma main, e executado pelo MR de validação !1 / pipeline 2961140139.

O job real 17270381689 confirmou cinco achados, todos pela regra
`generic-api-key`, com `--redact=100`: dois identificadores funcionais de
casos de teste foram confundidos com API key; uma senha sintética usada para
testar mascaramento foi interpretada como segredo estático; e o identificador
de arquivo Figma apareceu tanto no script E2E quanto no teste de contrato.
Nenhum valor detectado precisa ser publicado para realizar a correção.

## Incremento
Preservar o diagnóstico Gitleaks com `--verbose --no-color --redact=100`,
imagem por digest, `--source .`, `--no-git`, `.gitleaks.toml`, relatório
JSON e `--exit-code 1`.

Corrigir as cinco causas sem allowlist:
- renomear o seed de idempotência dos helpers de teste para não parecer uma API key;
- montar a credencial sintética do teste VBA em runtime, mantendo o teste de
  mascaramento sem armazenar um literal com aparência de segredo;
- nomear o Figma file key como `FIGMA_FILE_ID`, refletindo que é identificador
  e não credencial, sem alterar o valor ou o contrato funcional;
- impedir por teste de regressão a reintrodução dos padrões e a inclusão desses
  valores na allowlist Gitleaks.

## Critérios de aceite
- O contrato da configuração detecta comando silencioso, mascaramento parcial,
  alteração de escopo, ausência de política, exit code zero e `|| true`.
- Os testes funcionais afetados continuam aprovados.
- O teste preventivo comprova que os cinco padrões não reaparecem e que nenhum
  deles foi transferido para a allowlist.
- Pre-PR/CI executa no HEAD exato e a branch permanece atualizada.
- O MR temporário GitLab executa o Gitleaks real no conteúdo equivalente ao
  HEAD da PR, com mascaramento integral.
- O Gitleaks real retorna zero achados bloqueantes antes do merge no GitHub.
- Após merge governado, o mirror existente iguala os SHAs GitHub/GitLab e uma
  pipeline da main executa os gates obrigatórios sem transformar `skipped`
  em aprovação.

## Referência da interface
https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md

## Reversão
Reverter o incremento de diagnóstico/remediação como um conjunto; nunca
desabilitar o scanner, reduzir o escopo ou ampliar allowlists para obter verde.
