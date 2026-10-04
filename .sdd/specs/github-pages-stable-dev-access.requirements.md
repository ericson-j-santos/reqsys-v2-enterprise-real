# Acesso DEV estável pelo GitHub Pages

## Objetivo

Manter o frontend ReqSys DEV e o callback Microsoft em uma URL estável e gratuita no GitHub Pages, usando o locator Ed25519 somente para descobrir a API PC24x7 publicada por Cloudflare Quick Tunnel.

## Requisitos

- O navegador deve permanecer em `https://ericson-j-santos.github.io/reqsys-v2-enterprise-real/dev/`.
- O bundle deve usar base path `/reqsys-v2-enterprise-real/dev/`.
- O callback Microsoft deve ser `/reqsys-v2-enterprise-real/dev/auth/callback.html`.
- O endpoint da API deve ser aceito somente quando vier de envelope Ed25519 válido, vigente, DEV e limitado a `https://*.trycloudflare.com`.
- O runtime público deve desabilitar login demo e aceitar CORS apenas das origens explicitamente permitidas.
- Nenhum segredo pode ser publicado no Pages, locator, bundle ou artifact.

## Critérios de aceite

- O Pages entrega o frontend e o callback Microsoft na URL estável.
- O locator assinado resolve uma API DEV saudável sem mudar a URL visível.
- O backend aceita a origem Pages e mantém o login de demonstração desativado.
- Os testes, build, gate SDD e validação do runtime passam no mesmo commit.

## Evidência mínima

- Testes unitários do locator, MSAL e navegação.
- Build Vite com o base path do Pages.
- Testes dos contratos PC24x7.
- Resolver remoto comprovando assinatura e validade do locator.
- Configuração Entra preservando URIs existentes e acrescentando a callback Pages.
