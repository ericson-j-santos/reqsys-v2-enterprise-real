# Correção de 404 no GitHub Pages — ReqSys Showcase

## Sintoma

As URLs do GitHub Pages retornaram 404 após o merge da landing pública.

## Causa provável

O PR anterior adicionou a landing em:

```text
docs/public-showcase/reqsys-linkedin/index.html
```

E adicionou um workflow de GitHub Pages. Porém, após o merge, não houve execução de workflow associada ao commit de merge. Sem deploy efetivo, a URL via GitHub Pages continua retornando 404.

Além disso, caso o repositório esteja configurado no modo clássico `Deploy from branch` com pasta `/docs`, a página inicial esperada precisa existir em:

```text
docs/index.html
```

## Correção aplicada

Esta correção adiciona:

```text
docs/index.html
docs/assets/styles.css
docs/assets/favicon.svg
docs/assets/reqsys-og.svg
docs/.nojekyll
```

Com isso, o GitHub Pages clássico pode publicar a landing diretamente na raiz:

```text
https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/
```

## Configuração recomendada no GitHub

Em `Settings > Pages`:

1. Source: `Deploy from a branch`.
2. Branch: `main`.
3. Folder: `/docs`.
4. Save.

## URL esperada após publicação

```text
https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/
```

## Alternativa por GitHub Actions

Se preferir usar o workflow:

1. Em `Settings > Pages`, selecionar `GitHub Actions` como source.
2. Executar o workflow `Deploy ReqSys Public Showcase` manualmente ou fazer novo push em `main` alterando os arquivos do showcase.

## Validação

Após configurar Pages e aguardar a publicação:

- abrir a URL raiz;
- validar CSS carregado;
- validar imagem Open Graph;
- testar responsividade mobile;
- testar compartilhamento no LinkedIn Post Inspector.
