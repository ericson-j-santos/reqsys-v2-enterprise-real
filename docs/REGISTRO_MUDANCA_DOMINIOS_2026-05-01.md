# Registro de Mudanca - Dominios Dev e Prod

Data: 2026-05-01
Responsavel: Time de Plataforma / Copilot
Tipo: Infraestrutura + Configuracao de Aplicacao

## Resumo executivo

Foi realizada a padronizacao para uso de dominio proprio em ambientes de desenvolvimento e producao, removendo dependencia de localhost e reforcando seguranca de CORS no backend.

## Objetivo

- Permitir uso de dominios proprios em dev e prod
- Eliminar acoplamento em localhost/127.0.0.1 no consumo de API
- Controlar CORS por variavel de ambiente em vez de wildcard
- Manter compatibilidade com gateway reverso (/api)

## Mudancas aplicadas

### Backend

Arquivo: backend/app/core/config.py

- Adicionada propriedade cors_origins_list para transformar CORS_ORIGINS (csv) em lista efetiva de origens.

Arquivo: backend/app/main.py

- Incluida importacao de settings.
- CORS alterado de allow_origins=['*'] para allow_origins=settings.cors_origins_list.

### Frontend

Arquivo: frontend/src/services/api.js

- Base URL alterada de fallback localhost para fallback relativo /api.

Arquivo: frontend/.env

- VITE_API_URL atualizado para http://api.reqsys.local:8210 (dev local por dominio).

Arquivo: frontend/.env.example

- Exemplo atualizado para dominio de desenvolvimento local.

### Orquestracao

Arquivo: docker-compose.yml

- Backend passou a receber CORS_ORIGINS por variavel de ambiente.
- Frontend passou a receber VITE_API_URL configuravel com fallback /api.

### Configuracao de exemplo e guia

Arquivo: .env.example

- Incluidas variaveis de referencia para CORS_ORIGINS e VITE_API_URL com cenarios dev/prod.

Arquivo: README.md

- Adicionada secao "Dominios proprios (dev e prod)" com:
  - mapeamento de hosts no Windows
  - variaveis de ambiente necessarias
  - orientacoes de DNS e TLS para producao

## Arquivos impactados

- backend/app/core/config.py
- backend/app/main.py
- frontend/src/services/api.js
- frontend/.env
- frontend/.env.example
- .env.example
- docker-compose.yml
- README.md

## Validacao executada

- Compilacao Python: python -m compileall app
- Resultado: sem erros de sintaxe nos modulos alterados.

## Resultado esperado

- Desenvolvimento local por dominio (ex.: reqsys.local e api.reqsys.local)
- Producao por dominio publico com CORS restrito ao frontend oficial
- Menor risco de exposicao por CORS wildcard

## Rollback rapido

1. backend/app/main.py: voltar allow_origins para ['*'] (nao recomendado para prod)
2. frontend/src/services/api.js: restaurar fallback localhost
3. docker-compose.yml: remover CORS_ORIGINS e restaurar VITE_API_URL fixo
4. Restaurar .env/.env.example anteriores

## Pendencias operacionais

- Garantir entradas no hosts do Windows para dev local.
- Configurar DNS e TLS no ambiente produtivo.
- Validar politicas de CORS com dominio final de frontend.

## Endpoint de auditoria adicionado

### Adicao de API para consultar historico de mudancas

Arquivo: backend/app/api/auditoria.py

- Criado novo modulo com rotas GET para consulta de trilha de auditoria.
- Endpoints:
  - `GET /v1/auditoria/eventos` - lista todos eventos com filtros opcionais (entidade, acao, limite, offset)
  - `GET /v1/auditoria/eventos/config-infra` - lista especificamente mudancas de configuracao de infra (dominios, CORS, env)

Arquivo: backend/app/main.py

- Registrado novo router de auditoria.
- CORS mantido como settings.cors_origins_list (configuravel por variavel de ambiente).

### Exemplo de uso

```bash
# Listar ultimas mudancas de configuracao de infraestrutura
GET http://api.reqsys.local:8210/v1/auditoria/eventos/config-infra?limit=20

# Listar todos eventos com filtro
GET http://api.reqsys.local:8210/v1/auditoria/eventos?entidade=infra&acao=CONFIG_DOMINIO_ATUALIZADA&limit=10

# Resposta esperada
{
  "meta": { "correlation_id": "...", "timestamp": "..." },
  "data": {
    "config_historico": [
      {
        "id": 3,
        "correlation_id": "chg-dominios-20260501",
        "usuario": "copilot",
        "acao": "CONFIG_DOMINIO_ATUALIZADA",
        "entidade_id": "reqsys-v2",
        "payload_minimo": "{...mudancas...}",
        "criado_em": "2026-05-02T02:02:02"
      }
    ],
    "total": 1
  }
}
```
