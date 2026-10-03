# Runtime proprio portavel — substituicao do Fly.io

## Escopo e estado

Stack Linux independente para o nucleo ReqSys: FastAPI, frontend Vue compilado,
PostgreSQL, Redis persistente, gateway Nginx e HTTPS Caddy. PC24x7 e o destino
preferencial quando disponivel. O pacote pode ser movido para outro servidor
Linux com Docker Engine e Compose v2. Nao depende do Fly.io.

Preparacao de configuracao nao comprova migracao nem operacao em producao.
HML/PROD continuam bloqueados ate backup/restauracao, autenticacao, DNS/HTTPS,
seguranca, E2E e recuperacao apos reboot serem comprovados no host de destino.
O piloto Windows/Quick Tunnel existente permanece restrito a DEV.

## Custo e disponibilidade

Software gratuito. Energia, internet, dominio e backup externo podem custar.
Um servidor unico nao oferece alta disponibilidade. As imagens usam tags de
versao: antes de PROD registrar digests aprovados e atualizar por janela.
Quick Tunnel nao e ingresso de producao. CGNAT exige ingresso por tunnel nomeado
ou IP publico; Caddy sozinho nao resolve CGNAT.

## Preparacao Linux

1. Selecionar host, CPU/RAM/disco e capacidade por carga medida. Garantir espaco
   para banco, Redis, imagens e backups; configurar atualizacoes e firewall.
2. Docker Engine e plugin Compose v2 ja instalados; manter administracao por
   canal privado. Somente 80/443 publicos, sem portas de banco/API/Redis.
3. Criar diretorio externo privado e executar:
   `python3 scripts/init_self_hosted_secrets.py --directory /etc/reqsys/dev/secrets`.
   Diretorio 0700; arquivos 0600. Nunca commitar valores.
4. Copiar `infra/self-hosted/.env.example` para arquivo privado externo. Os
   parametros desse exemplo servem para ensaio localhost.
5. Para producao, escolher projeto exclusivo, APP_ENV=production, PUBLIC_ORIGIN
   HTTPS, SITE_ADDRESS com hostname real, email ACME real, BIND_ADDRESS=0.0.0.0,
   HTTP_PORT=80 e HTTPS_PORT=443. Configurar IDs Azure existentes e registrar
   o callback `PUBLIC_ORIGIN/auth/callback.html` no Entra ID.
6. Confirmar DNS/ingresso, identidade Azure, secrets e registry de fontes
   externas exigido pelos gates atuais do backend. Ausencia deve bloquear boot.

Validacao sem imprimir configuracao/segredos:

```bash
docker compose --env-file /etc/reqsys/dev/runtime.env -f infra/self-hosted/compose.yml config --quiet
```

Implantacao em ambiente isolado autorizado:

```bash
docker compose --env-file /etc/reqsys/dev/runtime.env -f infra/self-hosted/compose.yml up --build -d --wait --wait-timeout 300
```

Usar Command Gateway/control plane vigente para executar no host. Nao executar
sobre volumes do piloto existente. O nome do projeto isola redes e volumes.
Nenhum servico alem de Caddy publica portas. Demo login sempre desabilitado.
O usuario SQL da API nao e superusuario. Redis fica somente na rede interna.

## Backup e restauracao obrigatorios

Usar Restic com repositorio externo e senha em arquivo privado; inicializar
o repositorio apenas se novo. Configurar RESTIC_REPOSITORY, RESTIC_PASSWORD_FILE
e REQSYS_ENV_FILE fora do Git. Script:

```bash
bash infra/self-hosted/backup-postgres.sh
restic check
```

Backup nao prova restauracao. Em stack de ensaio isolada, recuperar dump
por ID de snapshot explicitamente escolhido; nunca usar PROD como destino:

```bash
restic dump SNAPSHOT_ID reqsys-postgres.dump > /diretorio-privado/reqsys-postgres.dump
docker compose --env-file /etc/reqsys/restore/runtime.env -f infra/self-hosted/compose.yml exec -T db pg_restore -U reqsys_owner -d reqsys --exit-on-error < /diretorio-privado/reqsys-postgres.dump
```

Restaurar em banco novo inicializado, verificar schema, contagens por tabela,
amostras e fluxos autenticados. Dump usa role reqsys_app criada no init-db.
Redis persistente precisa de backup separado se filas exigirem recuperacao;
validar consistencia de filas e trabalhos antes de corte. Inventariar arquivos,
uploads, cofre e servicos externos: o dump PostgreSQL nao cobre esses dados.
Definir RPO/RTO, agenda diaria de backup, alertas, retencao e teste recorrente
de restauracao. Nao habilitar prune sem politica de retencao aprovada.

## Migracao de todas as solucoes

| Solucao | Destino planejado | Gate de corte |
|---|---|---|
| ReqSys principal | Esta stack, projeto por ambiente | Banco, Azure, filas, E2E |
| GovBI IA | Compose proprio usando Dockerfile existente | SQL Server/cofre/identidade |
| ReqSys Java | Compose proprio usando Dockerfile existente | PostgreSQL/cofre/autenticacao |
| ReqSys Intake | Compose proprio com volume persistente | SQLite restaurado e consumidores |
| MCMV Rural | Infra Linux existente | Banco e frontend validados |
| VSCode Agent | Container do runtime existente | Health, ferramentas e persistencia |

Esta tabela e plano: nao afirma deploy desses outros produtos. Nao trocar URLs
por valores inventados. Cada consumidor deve usar URL comprovada e credencial
do mecanismo protegido existente.

Ordem por ambiente: inventariar fonte e consumidores; backup consistente;
restaurar no destino isolado; comparar dados; smoke e E2E autenticado; testar
restart/reboot; congelar escritas; sincronizacao final; mudar consumidores/DNS;
validar externamente; acompanhar; encerrar recursos Fly somente depois disso.
Rollback: manter backup final e release anterior no host proprio; nunca
reativar Fly. Nao usar `docker compose down -v` em ambiente com dados.

## Deploy e monitoramento

Inicialmente deploy pelo control plane autorizado com SHA revisado e CI verde.
Runner GitHub proprio somente para workflows confiaveis, dedicado a ambiente,
sem executar PR externo com acesso ao Docker socket. Nao instalar runner
automaticamente no notebook. Automacao de deploy fica pendente do host validado.

Uptime Kuma em host independente pode monitorar HTTPS, /api/health e expiracao
de certificado; o painel deve ficar privado. Monitoramento no mesmo servidor
nao detecta adequadamente a queda total dele. Implantacao e alertas exigem
destino e canal existentes; nenhum servico SaaS novo e presumido.
