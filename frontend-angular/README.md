# ReqSys Enterprise — Frontend Angular

Scaffold Angular 17 standalone components com Angular Material e tema escuro personalizado.

## Stack

| Tecnologia         | Versão |
| ------------------ | ------ |
| Angular            | 17.3.0 |
| Angular Material   | 17.3.0 |
| Angular CDK        | 17.3.0 |
| Angular Animations | 17.3.0 |
| RxJS               | 7.8    |
| TypeScript         | ~5.4   |

## Funcionalidades

- **Tema escuro** — fundo `#0d1117`, superfície `#161b22`, primária amber `#fbbf24`, accent indigo
- **Autenticação JWT** — token `reqsys_token` em localStorage, interceptor HTTP automático
- **RBAC** — guard de rotas por permissão (`data.permissao`)
- **Lazy loading** — cada view carregada sob demanda
- **Sidenav responsivo** — rail mode no desktop, overlay no mobile
- **Correlation ID** — header `X-Correlation-Id` em toda requisição

## Setup

```bash
npm install
npx ng serve       # http://localhost:4200
npx ng build       # dist/reqsys-angular/
```

## Proxy

O proxy `proxy.conf.json` redireciona `/api/*` → `http://localhost:8081`. Configurado em `angular.json` via `proxyConfig`.

## Credenciais de demonstração

| Perfil        | E-mail                | Senha       |
| ------------- | --------------------- | ----------- |
| Administrador | admin@reqsys.local    | admin123    |
| Analista      | analista@reqsys.local | analista123 |
| Auditor       | auditor@reqsys.local  | auditor123  |
