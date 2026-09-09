# Piloto PC 24x7 — ambiente dev

Runbook operacional do piloto descrito no [ADR-046](../adr/ADR-046-pc24x7-substituicao-flyio.md).
Escopo **restrito a dev** — hml e prod continuam no Fly.io até o piloto ser validado por um
período e uma decisão explícita ser tomada para os demais ambientes.

Todos os passos abaixo usam ferramentas gratuitas (nenhum custo de domínio, nuvem ou
armazenamento é necessário para rodar o piloto).

## 1. Pré-requisitos

- Docker + Docker Compose instalados no PC 24x7.
- Conta gratuita na Cloudflare (só para exposição pública e backup — ver seções 3 e 5).
- `cloudflared` instalado ([instruções oficiais](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)).

## 2. Subir a stack

A stack já existe e já foi validada localmente (PR #1557) — nada de novo aqui:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

O gateway nginx sobe em `http://localhost:${GATEWAY_PORT:-8081}` e já roteia `/api/*`
(backend) e `/` (frontend) — confirmar com:

```bash
curl http://localhost:8081/api/runtime/health
```

## 3. Expor publicamente — sem domínio, sem custo (fase 1)

Como não há domínio próprio ainda, a fase 1 usa o **Cloudflare Quick Tunnel**: gera uma URL
pública `https://<aleatório>.trycloudflare.com` sem precisar de conta paga, domínio ou
qualquer configuração de DNS.

```bash
cloudflared tunnel --url http://localhost:8081
```

A URL aparece no terminal (ex.: `https://exemplo-aleatorio.trycloudflare.com`) e pode ser
testada imediatamente:

```bash
curl https://<url-gerada>/api/runtime/health
```

**Limitação conhecida e aceita para o piloto:** essa URL é temporária — muda toda vez que o
`cloudflared` reinicia, e a Cloudflare não dá garantia de disponibilidade para Quick Tunnels
(são documentados como uso de teste, não produção). Isso é aceitável para o piloto de **dev**
porque o objetivo aqui é validar o caminho técnico (Docker + túnel + PC 24x7), não servir
usuários finais com URL estável.

### Fase 2 (quando houver orçamento): domínio próprio + túnel nomeado

Quando fizer sentido gastar (~R$40–60/ano por um domínio), o caminho fica assim:

1. Registrar um domínio em qualquer registrador.
2. Adicionar o domínio à Cloudflare (plano Free) e apontar os nameservers do registrador
   para a Cloudflare.
3. Criar um túnel nomeado (`cloudflared tunnel create reqsys-dev`) e uma rota DNS
   (`cloudflared tunnel route dns reqsys-dev dev.seudominio.com`) — isso substitui o Quick
   Tunnel por uma URL estável, sem os limites do modo de teste.

Esse passo é adiado deliberadamente: não faz sentido gastar em domínio antes de validar que o
resto do piloto (estabilidade do PC, backup, restart) funciona.

## 4. Restart automático após queda de energia/reinício

A stack já tem `restart: unless-stopped` em todos os serviços do `docker-compose.yml` — isso
garante que os containers voltam sozinhos **assim que o daemon do Docker sobe**. O que falta
garantir é que o **próprio Docker** suba sozinho com o sistema operacional, sem depender de
alguém logar fisicamente na máquina.

### Linux (recomendado para o PC 24x7 definitivo)

```bash
sudo systemctl enable docker
```

O Docker Engine no Linux roda como serviço `systemd` — sobe no boot do SO, sem precisar de
login de usuário. É o caminho mais robusto para uma máquina que passa por quedas de energia.

### Windows (o que está disponível hoje, para validar o piloto rapidamente)

Docker Desktop **não** roda como serviço do Windows — ele depende de uma sessão de usuário
logada. Duas opções, em ordem de recomendação:

1. **WSL2 + Ubuntu com systemd + Docker Engine nativo (sem Docker Desktop).** O WSL2 moderno
   suporta `systemd`, então dá para instalar o Docker Engine dentro de uma distro Ubuntu e
   habilitar `docker.service` exatamente como no Linux — isso inicia com o Windows sem exigir
   login de usuário. É o caminho recomendado se o PC 24x7 for continuar no Windows.
2. **Docker Desktop + login automático do Windows.** Habilitar "Start Docker Desktop when you
   sign in" nas configurações do Docker Desktop, e configurar login automático do Windows
   (`netplwiz` ou uma conta de serviço dedicada). **Ressalva de segurança:** login automático
   enfraquece a postura de segurança da máquina (a senha fica acessível a quem tiver acesso
   físico/à conta local) — aceitável só para o piloto de dev, não recomendado se este PC vier
   a hospedar hml/prod no futuro.

## 5. Backup — reaproveitando o padrão gratuito que o repositório já usa

O ReqSys já tem um pipeline de backup gratuito testado para BACEN-04
(`scripts/reqsys_free_tier_backup.py` + `scripts/run_reqsys_free_tier_backup.sh`): restic
como ferramenta de backup + Cloudflare R2 (10 GiB grátis, sem custo de egress) como
armazenamento externo criptografado. Esse padrão já é a resposta certa aqui — só não precisa
da parte de orquestração de Fly Machines (`flyctl ssh`/`machine start`/`stop`), porque no PC
24x7 o backup roda no mesmo host onde o banco já está.

`scripts/pc24x7_backup_restic.sh` (novo, ver este PR) faz a versão simplificada: dump do
Postgres via `docker compose exec`, backup com `restic`, retenção com `restic forget --prune`.

### Configuração (uma vez)

1. Criar um bucket R2 gratuito na Cloudflare (dashboard → R2 → Create bucket).
2. Gerar um token de API R2 (S3-compatible) com permissão de leitura/escrita nesse bucket.
3. Exportar as variáveis que o restic espera:

```bash
export RESTIC_REPOSITORY="s3:https://<account-id>.r2.cloudflarestorage.com/reqsys-dev-backup"
export RESTIC_PASSWORD="<senha-forte-para-criptografia-do-repositorio-restic>"
export AWS_ACCESS_KEY_ID="<r2-access-key-id>"
export AWS_SECRET_ACCESS_KEY="<r2-secret-access-key>"
```

### Rodando o backup

```bash
./scripts/pc24x7_backup_restic.sh
```

Recomendado agendar isso diariamente (`cron` no Linux, Agendador de Tarefas no Windows).

## 6. Critério de saída do piloto

Antes de considerar promover dev-no-PC24x7 para "principal" (e antes de sequer cogitar hml ou
prod), validar por um período (sugestão: pelo menos 2 semanas de uso real):

- URL pública respondendo de forma consistente (sem quedas não planejadas).
- Pelo menos uma restauração de backup testada com sucesso (`restic restore`), não só o
  backup em si.
- Reinício do PC (real ou simulado) seguido de recuperação automática dos containers sem
  intervenção manual.

Só depois disso faz sentido revisitar o ADR-046 para decidir sobre hml/prod.
