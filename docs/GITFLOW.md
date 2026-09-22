# GitFlow do ReqSys

Este projeto passa a seguir GitFlow leve, com versionamento semântico e changelog obrigatório antes de novas entregas funcionais.

## Branches permanentes

- `main`: código estável, liberado para produção.
- `develop`: integração de features aprovadas e testadas.

## Branches temporárias

| Tipo | Padrão | Uso |
| --- | --- | --- |
| Feature | `feature/<versao>-<descricao>` | Desenvolvimento incremental. |
| Release | `release/<versao>` | Congelamento, QA, changelog e preparação de tag. |
| Hotfix | `hotfix/<versao>-<descricao>` | Correção urgente a partir de `main`. |

## Fluxo obrigatório por release

1. Definir a versão em `VERSION` usando SemVer.
2. Atualizar `CHANGELOG.md` com data, escopo, testes e plano de rollback.
3. Criar branch `release/<versao>` a partir de `develop` quando houver branch de integração disponível.
4. Executar testes automatizados disponíveis no ambiente.
5. Abrir PR para `main` e marcar tag `v<versao>` após aprovação.
6. Fazer merge-back para `develop` quando `main` receber a release.

## Convenção de commits

- `feat:` novas funcionalidades.
- `fix:` correções.
- `docs:` documentação.
- `test:` testes.
- `chore:` versionamento, build e manutenção.

## Checklist de confirmação antes de implementar feature

- [ ] Versão definida em `VERSION`.
- [ ] Changelog atualizado.
- [ ] Branch compatível com GitFlow identificada ou criada.
- [ ] Plano de testes documentado.
- [ ] Rollback descrito no changelog.
