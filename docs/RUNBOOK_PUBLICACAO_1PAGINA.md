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
# frontend/.env -> VITE_API_URL=http://localhost:8081/api
# .env -> CORS_ORIGINS=http://reqsys.local:5182,http://localhost:8081
```
3. Subir stack:
```bash
./scripts/publicar_ambiente.sh dev
```
4. Validar saúde e acesso:
```bash
./scripts/testar_urls_ambiente.sh dev
```

**URLs DEV**
- Frontend: http://localhost:8081
- API: http://localhost:8081/api
- Health: http://localhost:8081/api/health

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
./scripts/publicar_ambiente.sh hml
```
5. Validação:
```bash
./scripts/testar_urls_ambiente.sh hml
```

**URLs HOMOLOGAÇÃO**
- Frontend: https://hml-app.seudominio.com
- API: https://hml-api.seudominio.com
- Health: https://hml-api.seudominio.com/api/health

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
./scripts/publicar_ambiente.sh prod
```
5. Health e verificação funcional:
```bash
./scripts/testar_urls_ambiente.sh prod
```

**URLs PRODUÇÃO**
- Frontend: https://app.seudominio.com
- API: https://api.seudominio.com
- Health: https://api.seudominio.com/api/health

---

## 4) Gate de qualidade (antes de publicar)
```bash
./scripts/validar_qualidade.sh
```

Cobertura do gate:
- Testes backend (pytest)
- Build frontend (Vue/Vuetify + Angular)
- E2E login + acessibilidade (labels, navegação por teclado, fluxo de autenticação)

## 5) Domínio gratuito (opções práticas)
- `duckdns.org`: subdomínios gratuitos (ex.: `meuapp.duckdns.org`) com atualização dinâmica.
- `nip.io` / `sslip.io`: domínios dinâmicos que resolvem para IP (ótimos para testes rápidos).
- `noip.com` (plano free): hostname gratuito com renovação periódica.

> Para ambiente público use HTTPS obrigatório com certificado válido (Let's Encrypt é gratuito).

## 6) Rollback rápido
```bash
git checkout <tag_ou_commit_estavel>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```


## Observação importante sobre stack local
- O `docker-compose.yml` atual possui serviço `kb` com build em `../../kb`; garanta esse diretório antes do `up --build`, ou ajuste/override para ambiente local.
