# Publicação — Portal de Governança Padrão Ouro

## Data

2026-06-20

## Objetivo

Registrar a publicação da melhoria de governança padrão ouro como tela navegável do frontend ReqSys.

## URL publicada

```text
https://reqsys-app.fly.dev/governanca
```

## URLs por ambiente

| Ambiente | URL |
|---|---|
| Produção | `https://reqsys-app.fly.dev/governanca` |
| Homologação | `https://reqsys-app-stg.fly.dev/governanca` |
| Desenvolvimento | `https://reqsys-app-dev.fly.dev/governanca` |

## Arquivos alterados

- `frontend/src/views/GovernancaEnterpriseView.vue`
- `frontend/src/router/index.js`

## Capacidade entregue

A tela `/governanca` consolida:

- ciclo operacional padrão ouro;
- gates bloqueantes de produção;
- observabilidade mínima;
- analytics e drill-down;
- IA auditável;
- ambientes e URLs operacionais.

## Segurança

- Não altera autenticação.
- Não altera CORS.
- Não altera JWT.
- Não altera secrets.
- Rota protegida por `dashboard:read`.

## Evidência de código

A rota `/governanca` foi registrada no router do frontend e aponta para `GovernancaEnterpriseView`.

## Observação de CI/CD

Até o momento do registro, os commits finais consultados não retornaram status/check-run vinculado pela ferramenta de GitHub. Isso deve ser tratado como validação pendente, não como CI verde confirmado.

## Próximo incremento recomendado

- adicionar item de menu lateral para `/governanca`;
- validar build do frontend;
- acionar ou corrigir pipeline de deploy;
- verificar acesso real em produção;
- criar monitoramento sintético HTTP para `/governanca`.
