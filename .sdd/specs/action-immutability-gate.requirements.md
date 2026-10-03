# Action Immutability Gate — Requisitos

## Objetivo

Impedir que workflows novos ou alterados executem GitHub Actions externas por tags,
branches ou outras referências mutáveis, reduzindo o risco de alteração silenciosa
da cadeia de CI/CD sem commit correspondente no ReqSys.

## Estratégia de adoção

O repositório possui centenas de workflows legados. O gate deve sempre inventariar
todo o diretório `.github/workflows`, mas aplicar bloqueio fail-closed aos workflows
novos ou alterados no diff contra `main`. Ao tocar um workflow legado, todas as
referências externas `uses:` desse arquivo devem ser migradas para referência
imutável no mesmo incremento.

## Requisitos

1. Ações locais iniciadas por `./` são a única exceção explícita ao pin por SHA.
2. Actions e reusable workflows externos devem usar SHA Git hexadecimal completo de 40 caracteres.
3. Referências `@vN`, tags semânticas, `@main`, `@master` e refs ausentes devem falhar.
4. Referências `docker://` devem usar digest `sha256` de 64 caracteres hexadecimais.
5. O relatório deve registrar o inventário de violações de todo o repositório e separar as violações bloqueantes do diff.
6. O Pre-PR Readiness deve executar o gate como invariante preventiva vinculada ao HEAD atual.
7. O próprio workflow Pre-PR alterado por este incremento deve usar SHAs imutáveis.
8. O controle negativo deve provar que `actions/checkout@v4` é rejeitado.
9. Nenhum deploy, segredo, permissão adicional ou alteração de ambiente pode ser introduzido.

## Critérios de aceite

- Testes unitários do gate verdes, incluindo controles negativos.
- `python scripts/validate_action_immutability.py --self-test-negative` retorna sucesso somente quando a referência mutável é detectada.
- Pre-PR Readiness verde no HEAD final.
- Relatório do gate sem violações bloqueantes no diff do HEAD final.
