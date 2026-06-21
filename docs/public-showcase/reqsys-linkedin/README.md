# ReqSys — Showcase público para LinkedIn

Este diretório contém uma versão pública, estática e sanitizada do ReqSys para publicação via URL no LinkedIn.

## Decisão

Publicar uma landing pública em vez de expor a aplicação operacional completa.

## Objetivo

Apresentar o ReqSys como iniciativa/produto de engenharia de requisitos corporativa com IA, rastreabilidade, governança, analytics e documentação viva.

## Conteúdo

```text
index.html
assets/styles.css
assets/favicon.svg
assets/reqsys-og.svg
README.md
```

## Segurança e governança

Este material não deve conter:

- dados reais;
- credenciais;
- tokens;
- tenants;
- client ids;
- endpoints internos;
- prints sensíveis;
- logs;
- payloads reais;
- nomes de clientes;
- integrações administrativas.

## Execução local

```bash
cd docs/public-showcase/reqsys-linkedin
python -m http.server 8080
```

Acesso local:

```text
http://localhost:8080
```

## Publicação recomendada

Opções adequadas:

1. GitHub Pages apontando para este diretório ou para uma cópia em `/docs`.
2. Vercel com projeto estático.
3. Netlify Drop.
4. Cloudflare Pages.

## URL esperada

A URL final depende da configuração do host. Exemplo com GitHub Pages:

```text
https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/public-showcase/reqsys-linkedin/
```

Caso o GitHub Pages publique diretamente a pasta `docs`, o caminho poderá variar conforme a configuração do repositório.
