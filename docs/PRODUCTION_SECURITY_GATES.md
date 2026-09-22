# Gates de segurança para produção — ReqSys v2 Enterprise Real

## Objetivo

Garantir que a API não suba em modo produção quando configurações mínimas de segurança estiverem ausentes ou inseguras.

Este documento registra a decisão aplicada no incremento `fix/prod-security-gates`.

## Gates bloqueantes

Quando `APP_ENV` estiver como `production`, `prod` ou `prd`, o backend deve bloquear o startup se qualquer condição abaixo ocorrer:

| Gate | Condição bloqueante | Mitigação |
| --- | --- | --- |
| JWT secret fraco | `JWT_SECRET` ausente, padrão ou com menos de 32 caracteres | Gerar segredo forte via `python -c "import secrets; print(secrets.token_hex(32))"` |
| Expiração JWT inválida | `JWT_EXP_MINUTES <= 0` em produção | Definir valor positivo, exemplo: `JWT_EXP_MINUTES=60` |
| Issuer ausente | `JWT_ISSUER` vazio | Definir emissor canônico, exemplo: `reqsys-api` |
| Audience ausente | `JWT_AUDIENCE` vazio | Definir público canônico, exemplo: `reqsys-frontend` |
| Login demo ativo | `ALLOW_DEMO_LOGIN=true` em produção | Usar `ALLOW_DEMO_LOGIN=false` |
| CORS aberto | `CORS_ORIGINS=*` em produção | Declarar origens explícitas, exemplo: `https://tieriprod.duckdns.org` |

## Variáveis mínimas para produção

```env
APP_ENV=production
ALLOW_DEMO_LOGIN=false
JWT_SECRET=<segredo-forte-minimo-32-caracteres>
JWT_ISSUER=reqsys-api
JWT_AUDIENCE=reqsys-frontend
JWT_EXP_MINUTES=60
CORS_ORIGINS=https://tieriprod.duckdns.org
```

## Decisão de arquitetura

- Desenvolvimento continua podendo usar login demo controlado para testes locais.
- Produção passa a exigir configuração explícita de identidade do token (`iss` e `aud`).
- Produção passa a exigir tempo de expiração JWT positivo para impedir tokens inválidos ou sem janela operacional controlada.
- O backend falha cedo, durante o boot, em vez de subir com configuração insegura.
- O `docker-compose.prod.yml` exige as variáveis críticas por interpolação obrigatória.

## Critérios de aceite

- Com `APP_ENV=production` e `JWT_SECRET` fraco, o startup deve falhar.
- Com `APP_ENV=production` e `JWT_EXP_MINUTES <= 0`, o startup deve falhar.
- Com `APP_ENV=production` e `CORS_ORIGINS=*`, o startup deve falhar.
- Com `APP_ENV=production` e `ALLOW_DEMO_LOGIN=true`, o startup deve falhar.
- Com `JWT_ISSUER` e `JWT_AUDIENCE` configurados, tokens emitidos pelo backend devem conter e validar `iss`/`aud`.
- Com configuração segura, `validate_production_gates()` não deve lançar exceção.

## Testes adicionados

Arquivos principais:

- `backend/tests/test_security_production_gates.py`
- `backend/tests/test_security_production_gates_individual.py`
- `backend/tests/test_security_auth_jwt_individual.py`
- `backend/tests/test_security_cors_individual.py`

Cobertura principal:

- bloqueio de configuração insegura em produção;
- bloqueio individual de `JWT_EXP_MINUTES` zero ou negativo;
- aceite de configuração segura;
- emissão de JWT com `iss`, `aud`, `iat` e `exp`;
- validação real de `issuer` e `audience` no decode do JWT;
- rejeição de token expirado;
- bloqueio de CORS wildcard em produção.
