# Testes de Endpoints de Sistema

## Opção 1: Testar com cURL (Recomendado)

### 1. Obter documentação completa (sem autenticação)

```bash
curl -X GET http://api.reqsys.local:8210/v1/sistema/info
```

### 2. Fazer login para obter token JWT

```bash
curl -X POST http://api.reqsys.local:8210/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "ericsonjosedossantos@tieri659.onmicrosoft.com",
    "senha": "admin123"
  }'
```

Salve o token obtido em `<SEU_TOKEN>`.

### 3. Testar health-check (requer token)

```bash
curl -X GET http://api.reqsys.local:8210/v1/sistema/health-check \
  -H "Authorization: Bearer <SEU_TOKEN>"
```

### 4. Listar endpoints (sem autenticação)

```bash
curl -X GET http://api.reqsys.local:8210/v1/sistema/endpoints
```

### 5. Verificar dashboard info (requer token)

```bash
curl -X GET http://api.reqsys.local:8210/v1/dashboard/info \
  -H "Authorization: Bearer <SEU_TOKEN>"
```

### 6. Verificar configuração de infraestrutura (requer token)

```bash
curl -X GET http://api.reqsys.local:8210/v1/auditoria/eventos/config-infra \
  -H "Authorization: Bearer <SEU_TOKEN>"
```

---

## Opção 2: Testar com Postman

### Importar endpoints de teste

1. Abrir Postman
2. Criar nova collection: "ReqSys API Tests"
3. Adicionar os seguintes requests:

#### Request 1: Get API Info

```
GET http://api.reqsys.local:8210/v1/sistema/info
```

#### Request 2: Login

```
POST http://api.reqsys.local:8210/v1/auth/login
Content-Type: application/json

{
  "email": "ericsonjosedossantos@tieri659.onmicrosoft.com",
  "senha": "admin123"
}
```

#### Request 3: Health Check

```
GET http://api.reqsys.local:8210/v1/sistema/health-check
Authorization: Bearer {{token}}
```

#### Request 4: List Endpoints

```
GET http://api.reqsys.local:8210/v1/sistema/endpoints
```

#### Request 5: Dashboard Info

```
GET http://api.reqsys.local:8210/v1/dashboard/info
Authorization: Bearer {{token}}
```

#### Request 6: Auditoria Config

```
GET http://api.reqsys.local:8210/v1/auditoria/eventos/config-infra
Authorization: Bearer {{token}}
```

---

## Opção 3: Script Python

```python
import requests
import json

BASE_URL = "http://api.reqsys.local:8210"

# Credenciais de teste
CREDENTIALS = {
    "email": "ericsonjosedossantos@tieri659.onmicrosoft.com",
    "senha": "admin123"
}

# 1. Obter documentação
print("1. Documentação Completa da API")
print("=" * 60)
response = requests.get(f"{BASE_URL}/v1/sistema/info")
info = response.json()
print(json.dumps(info, indent=2, ensure_ascii=False))

# 2. Fazer login
print("\n2. Autenticação")
print("=" * 60)
response = requests.post(f"{BASE_URL}/v1/auth/login", json=CREDENTIALS)
auth_data = response.json()
token = auth_data['data']['token']
print(f"✅ Token obtido: {token[:20]}...")

# 3. Health Check
print("\n3. Health Check")
print("=" * 60)
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(f"{BASE_URL}/v1/sistema/health-check", headers=headers)
health = response.json()
print(json.dumps(health, indent=2, ensure_ascii=False))

# 4. Listar Endpoints
print("\n4. Lista de Endpoints")
print("=" * 60)
response = requests.get(f"{BASE_URL}/v1/sistema/endpoints")
endpoints = response.json()
print(json.dumps(endpoints, indent=2, ensure_ascii=False))

# 5. Dashboard Info
print("\n5. Informações do Dashboard")
print("=" * 60)
response = requests.get(f"{BASE_URL}/v1/dashboard/info", headers=headers)
dashboard = response.json()
print(json.dumps(dashboard, indent=2, ensure_ascii=False))

# 6. Auditoria de Configuração
print("\n6. Auditoria de Configuração de Infraestrutura")
print("=" * 60)
response = requests.get(f"{BASE_URL}/v1/auditoria/eventos/config-infra", headers=headers)
auditoria = response.json()
print(json.dumps(auditoria, indent=2, ensure_ascii=False))

print("\n✅ Todos os endpoints testados com sucesso!")
```

Para executar:

```bash
python test_endpoints.py
```

---

## Opção 4: Windows PowerShell

```powershell
$BaseUrl = "http://api.reqsys.local:8210"
$Credentials = @{
    email = "ericsonjosedossantos@tieri659.onmicrosoft.com"
    senha = "admin123"
}

# 1. Info
Write-Host "1. API Info"
Invoke-RestMethod -Uri "$BaseUrl/v1/sistema/info" | ConvertTo-Json -Depth 10

# 2. Login
Write-Host "`n2. Login"
$LoginResponse = Invoke-RestMethod -Uri "$BaseUrl/v1/auth/login" -Method Post -Body ($Credentials | ConvertTo-Json) -ContentType "application/json"
$Token = $LoginResponse.data.token

# 3. Health Check
Write-Host "`n3. Health Check"
$Headers = @{"Authorization" = "Bearer $Token"}
Invoke-RestMethod -Uri "$BaseUrl/v1/sistema/health-check" -Headers $Headers | ConvertTo-Json -Depth 10

# 4. Endpoints
Write-Host "`n4. Endpoints"
Invoke-RestMethod -Uri "$BaseUrl/v1/sistema/endpoints" | ConvertTo-Json -Depth 10

# 5. Dashboard
Write-Host "`n5. Dashboard Info"
Invoke-RestMethod -Uri "$BaseUrl/v1/dashboard/info" -Headers $Headers | ConvertTo-Json -Depth 10
```

---

## Resultados Esperados

### 1. GET /v1/sistema/info

```json
{
  "ok": true,
  "data": {
    "api_version": "2.2.0",
    "titulo": "ReqSys Enterprise API",
    "endpoints": {
      "health": {...},
      "login": {...},
      ...
    },
    "credenciais_demo": {
      "email": "ericsonjosedossantos@tieri659.onmicrosoft.com",
      "senha": "admin123"
    }
  }
}
```

### 2. GET /v1/sistema/health-check

```json
{
  "ok": true,
  "data": {
    "timestamp": "2026-05-02T02:22:39.xxx",
    "saude_geral": "ok",
    "componentes": {
      "database": {"status": "ok", "requisitos_total": 0},
      "config": {"status": "ok", "cors_configurado": true},
      "endpoints": {...}
    }
  }
}
```

### 3. GET /v1/sistema/endpoints

```json
{
  "ok": true,
  "data": {
    "total_endpoints": 8,
    "endpoints": [
      {
        "id": "health",
        "metodo": "GET",
        "url": "/health",
        "descricao": "Status da API",
        "autenticacao_requerida": false
      },
      ...
    ]
  }
}
```

---

## Verificações Manual

Para verificar via browser:

1. **Info Completa** (copy-paste na URL do browser)
   - `http://api.reqsys.local:8210/v1/sistema/info`
2. **Lista Endpoints** (copy-paste na URL do browser)
   - `http://api.reqsys.local:8210/v1/sistema/endpoints`

3. **Health Check e Dashboard** (requerem token, use cURL ou Postman)

---

## Solução de Problemas

### "Connection refused" - Não consigo acessar a API

- Verifique se o backend está rodando: `docker ps` deve mostrar container do backend
- Verifique se o Docker Compose está rodando: `docker-compose up` na pasta do projeto

### "404 Not Found" - Endpoint não encontrado

- Verifique a URL exata (case-sensitive)
- Certifique-se de que `sistema.router` foi registrado em `main.py`

### "401 Unauthorized" - Token inválido

- Faça o login novamente com as credenciais corretas
- Verifique se está usando o header `Authorization: Bearer <token>` corretamente

### "CORS error" no frontend

- Verifique se `CORS_ORIGINS` está configurado corretamente no .env
- Reinicie o backend após mudanças de CORS
