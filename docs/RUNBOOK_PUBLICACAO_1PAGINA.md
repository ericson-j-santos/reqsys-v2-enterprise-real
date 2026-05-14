# Runbook de Publicação (1 página) — Dev → Homologação → Produção

## 0) Pré-check (obrigatório)
```bash
# na raiz do repo
python3 --version
node --version
docker --version
docker compose version
```

## 1) Ambiente DEV (local com domínio)
1. Hosts locais:
```text
127.0.0.1 reqsys.local
127.0.0.1 api.reqsys.local
```
2. Variáveis:
```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
# ajustar:
# frontend/.env -> VITE_API_URL=http://api.reqsys.local:8210
# .env -> CORS_ORIGINS=http://reqsys.local:5182,http://reqsys.local:8082
```
3. Subir stack:
```bash
docker compose up --build -d
```
4. Smoke:
```bash
curl -fsS http://localhost:8210/health
curl -fsS http://localhost:8082
```

**URLs DEV**
- Frontend: http://reqsys.local:8082
- API: http://api.reqsys.local:8210
- Health: http://api.reqsys.local:8210/health

---

## 2) Homologação (staging)
1. Provisionar DNS interno:
- `hml-app.seudominio.com`
- `hml-api.seudominio.com`
2. Configurar TLS no proxy/Nginx.
3. Variáveis do ambiente:
```text
VITE_API_URL=https://hml-api.seudominio.com
CORS_ORIGINS=https://hml-app.seudominio.com
```
4. Deploy:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```
5. Validação:
```bash
curl -fsS https://hml-api.seudominio.com/health
```

**URLs HOMOLOGAÇÃO**
- Frontend: https://hml-app.seudominio.com
- API: https://hml-api.seudominio.com
- Health: https://hml-api.seudominio.com/health

---

## 3) Produção
1. DNS final:
- `app.seudominio.com`
- `api.seudominio.com`
2. TLS válido (Let's Encrypt/AC corporativo) + redirect HTTP→HTTPS.
3. Variáveis:
```text
VITE_API_URL=https://api.seudominio.com
CORS_ORIGINS=https://app.seudominio.com
```
4. Deploy:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```
5. Health e verificação funcional:
```bash
curl -fsS https://api.seudominio.com/health
curl -fsS https://api.seudominio.com/v1/sistema/health-check
```

**URLs PRODUÇÃO**
- Frontend: https://app.seudominio.com
- API: https://api.seudominio.com
- Health: https://api.seudominio.com/health

---

## 4) Gate de qualidade (antes de publicar)
```bash
# backend
cd backend && PYTHONPATH=. pytest -q

# e2e + acessibilidade + UX básico (login, navegação, labels)
cd .. && npm run test:e2e
```

## 5) Rollback rápido
```bash
git checkout <tag_ou_commit_estavel>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```
