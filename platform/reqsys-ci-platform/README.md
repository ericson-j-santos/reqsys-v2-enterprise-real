# reqsys-ci-platform — seed de extração

Este diretório é o conteúdo inicial do futuro repositório
`ericson-j-santos/reqsys-ci-platform`.

Ele permanece fora de `.github/workflows` no monorepo para **não criar mais um
workflow ativo** durante a migração.

## Responsabilidade

- reusable workflows;
- actions compostas;
- contratos de CI;
- validações determinísticas compartilhadas;
- versionamento/pinning por SHA completo;
- documentação de inputs, outputs e rollback.

## Regra de consumo

Depois que o repositório alvo existir, consumidores devem referenciar reusable
workflows por SHA completo. Tags podem existir para navegação humana, mas não são
evidência imutável para gates.

## Primeiro template

`workflows/python-quality.yml` é o primeiro reusable workflow portável. No
repositório alvo ele deve ser materializado em
`.github/workflows/python-quality.yml`.

O template não contém segredos e exige que o chamador forneça o comando de teste.
