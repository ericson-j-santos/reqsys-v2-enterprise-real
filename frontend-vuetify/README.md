# ReqSys Enterprise — Frontend Vuetify

Frontend melhorado em **Vue 3 + Vite + Vuetify 3** para o sistema ReqSys.

## Stack

| Pacote     | Versão  |
| ---------- | ------- |
| Vue        | ^3.5.13 |
| Vite       | ^6.2.1  |
| Vuetify    | ^3.7.15 |
| Pinia      | ^2.3.0  |
| Vue Router | ^4.5.0  |
| Axios      | ^1.7.9  |

## Funcionalidades

- Tema escuro customizado (`reqsysDark`) com paleta GitHub-like
- Sidebar responsiva: rail/mini em desktop, drawer temporário em mobile
- Breadcrumbs automáticos por rota
- RBAC via Pinia store + guarda de rota
- Interceptor Axios com `X-Correlation-Id` e JWT Bearer
- 8 views: Dashboard, Requisitos, Pipeline, Qualidade IA, Relatórios, Segredos, Rastreabilidade, Auditoria

## Desenvolvimento

```bash
npm install
npm run dev        # http://localhost:5174
```

## Build

```bash
npm run build
npm run preview
```

## Variáveis de ambiente

Crie `.env.local` se quiser sobrescrever a URL da API:

```
VITE_API_URL=http://localhost:8081/api
```

Por padrão, o Vite proxia `/api` → `http://localhost:8081`.

## Credenciais de demo

| Papel    | E-mail                | Senha       |
| -------- | --------------------- | ----------- |
| Admin    | admin@reqsys.local    | admin123    |
| Analista | analista@reqsys.local | analista123 |
| Auditor  | auditor@reqsys.local  | auditor123  |
