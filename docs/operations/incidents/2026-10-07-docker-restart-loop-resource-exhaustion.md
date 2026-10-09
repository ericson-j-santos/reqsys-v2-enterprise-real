# Incidente: esgotamento de recursos por loops Docker locais

Data: 2026-10-07

Computador analisado: estacao local (identificadores redigidos)

Status: incidente principal contido; controles permanentes preparados; pendencias inventariadas

Rastreabilidade: issue #2499; `OPS-GAP-DOCKER-RESTART-20261008`

Horarios abaixo usam `America/Sao_Paulo` (UTC-03), salvo quando UTC estiver
indicado explicitamente.

## Impacto

- CPU observada entre 96% e 100% nos picos de uma coleta separada do host.
- As amostras preservadas ao redor da contencao mostraram entre 0,72 e 1,0 GiB
  de memoria fisica disponivel em 15,7 GB.
- O pagefile tinha aproximadamente 9,1 GiB em uso e houve paginacao intensa.
- O compartilhamento de arquivos Windows/WSL manteve mais de um nucleo ocupado.
- A estacao ficou operacionalmente inviavel.

O SSD permaneceu saudavel, com espaco livre e sem fila ou erros relevantes. O
gargalo foi CPU, memoria e paginacao, amplificados por stacks Docker duplicadas.

## Causa principal

O container `reqsys-test-frontend-1` montava como `/app` a pasta local
`reqsys-v2-enterprise-real/frontend`. Essa arvore estava incompleta: continha
apenas `node_modules`, sem `package.json`, Dockerfiles ou arquivos Compose.

Como o arquivo Compose base aplicava `restart: unless-stopped` tambem a
dev/test, o comando `npm run dev` falhava com `ENOENT /app/package.json` e era
reiniciado indefinidamente. Foram registrados **6.991 reinicios** antes da
contencao.

## Contencao executada

Nenhum container ou volume foi removido.

1. `reqsys-test-frontend-1` foi parado e sua restart policy foi alterada para
   `no`.
2. Sinais de uso de `reqsys-test`, `github-main` e `ai-metrics-dev` foram
   verificados por portas, conexoes TCP, logs, trafego e dependencias de rede.
3. A amostra observada nao indicou uso ativo desses projetos. `github-main`
   tambem estava quebrado e `ai-metrics-dev` mantinha apenas watchers locais.
4. Os 11 containers desses projetos foram mantidos para rollback, mas ficaram
   nao ativos e com restart policy `no`.
5. Ambientes live/prod, tuneis, Redmine e servicos 24x7 permaneceram ativos.

Resultado imediato medido:

- containers ativos: 26 -> 17;
- em uma coleta posterior do host, CPU media de 66,5% (56% a 86%);
- memoria fisica disponivel entre 0,72 e 0,90 GiB, com aproximadamente 94,9%
  em uso;
- paginacao media de 2.915 paginas/s, cerca de 73% abaixo da referencia de
  10.903 paginas/s observada durante a saturacao.

A memoria do host continua pressionada por aplicativos e servicos residentes;
isso e uma frente separada do loop Docker corrigido.

## Controles permanentes implementados

- O Compose base agora usa `restart: "no"` para todos os servicos.
- Apenas `docker-compose.prod.yml` habilita recuperacao automatica, limitada a
  cinco falhas consecutivas de startup com `restart: "on-failure:5"`.
- Dev/test falham uma vez e tornam a causa visivel; producao recupera falhas
  transitorias sem repetir indefinidamente uma falha imediata de startup.
- O novo preflight `scripts/testar-preflight-docker.ps1` exige arquivos Compose,
  Dockerfiles, `frontend/package.json` e configuracao nginx antes de qualquer
  subida.
- Entrypoints locais usam projeto e overlay explicitos, executam
  `docker compose config --quiet` e aguardam health/readiness.
- O Task Scheduler passou a ser opt-in com `-HabilitarAgendamento`, usa
  `AtLogon` por padrao e nao solicita privilegio elevado.
- A auditoria `scripts/auditar-runtime-docker-local.ps1` identifica loops,
  unhealthy, binds ausentes ou com tipo incompativel, Compose ausente, restart
  persistente de dev e assinaturas de erro conhecidas sem salvar conteudo bruto
  de logs.
- Testes de contrato impedem a regressao das restart policies e do preflight.

## Pendencias encontradas e preservadas para tratamento

### Criticas

- `reqsys-dev-gateway-tunnel` e `reqsys-dev-failover-tunnel` continuam ativos,
  mas produziram 226 erros `Unauthorized: Tunnel not found` nas janelas moveis
  de 30 minutos observadas entre 07:30:16 e 07:32:17 (108 no gateway e 118 no
  failover).
  Foram preservados conforme a orientacao de manter os tuneis. Precisam de
  reconciliacao do tunnel ID/token e rotacao de logs.

### Altas

#### Jobs recorrentes quebrados

Snapshot do Task Scheduler as 07:22; os campos de proxima execucao abaixo
representam aquele momento, nao estado em tempo real.

| Tarefa | Frequencia / proxima execucao | Ultima execucao / resultado | Causa observada |
| --- | --- | --- | --- |
| `ReqSys-Dev-Runtime-Supervisor` | A cada 5 min; 07:27 | 07:22; `1` (`0x00000001`) | `run-dev-supervisor.cmd` aponta para `<USERPROFILE>\AppData\Local\Programs\Python\Python312\python.exe`, inexistente. |
| `ReqSysOrchestrator24x7` | Intervalo observado de 5 min; 07:26:42 | 07:21:44; `2147942402` (`0x80070002`) | Aponta para o mesmo Python 3.12 inexistente; arquivo nao encontrado. |
| `ReqSys-QualidadeIA-Snapshot-Diario` | Diaria; 08:00 | Horario nao registrado; `2147942667` (`0x8007010B`) | Acao malformada: `powershell.exe ... -File \`. |
| `ReqSys<HOST>ControlPlaneWatchdog` (nome redigido) | Nao determinada; sem proxima execucao | Horario nao registrado; `103` (`0x00000067`) | Sem proxima execucao; causa ainda nao confirmada. |

O supervisor e o provavel owner da reconciliacao dos tuneis e da publicacao do
locator. Seus dois logs, com aproximadamente 5,8 MB e 1,2 MB, continuam
recebendo `python.exe nao e reconhecido`. Nenhuma dessas tarefas foi alterada ou
desabilitada: os servicos 24x7 e os tuneis devem permanecer, e a correcao deve
comecar pelas acoes/caminhos sem mudar a politica de disponibilidade.

#### Runtime Docker

- O incidente de 6.991 reinicios permanece como
  `historical-restart-storm` de severidade alta, preservando rastreabilidade sem
  fazer o gate critico falhar para sempre por um container ja parado.
- Sete containers ativos apontam para arquivos Compose que nao existem mais:
  `reqsys-prod-api-1`, `reqsys-prod-frontend-1`, `reqsys-prod-kb-1`,
  `reqsys-dev-kb-1`, `reqsys-v2-enterprise-real-kb-1`, `redmine-app` e
  `redmine-db`.
- A auditoria corrigida encontrou 10 origens de bind realmente ausentes e tres
  incompatibilidades de tipo. `redmine-proxy` espera um arquivo `Caddyfile`, e
  `reqsys-prod-nginx-1`/`reqsys-test-nginx-1` esperam arquivos `.conf`, mas as
  tres origens existem como diretorios. Dois binds de `init-db.sh` que antes
  apareciam como ausentes foram confirmados como arquivos depois da conversao
  de `/run/desktop/mnt/host/<drive>/...` para caminho Windows.
- Nenhum dos 17 containers ativos possui limites de CPU, memoria ou PIDs.
- Todos os 17 ativos usam `json-file` sem rotacao persistida no container atual.
  O Compose ReqSys corrigido ja define rotacao para futuras recriacoes.
- Existem quatro instancias de KB simultaneas.
- `reqsys-live-api-1` monta uma arvore `.sdd` vazia, embora esteja healthy.
- Em uma coleta manual anterior, por volta de 06:57, Docker ocupava
  aproximadamente 55,62 GB em imagens, 35,37 GB em build cache (18,89 GB
  recuperaveis) e 3,19 GB em volumes. Nenhuma limpeza foi executada, pois exige
  decisao explicita de retencao.

## Evidencia preservada

- `artifacts/local-docker-runtime-audit/docker-runtime-audit-20261007-073217.json`
- `artifacts/local-docker-runtime-audit/docker-runtime-audit-20261007-073217.md`

A coleta Docker comecou em `2026-10-07T10:30:16Z` e terminou em
`2026-10-07T10:32:17Z` (07:30:16 a 07:32:17 local). As contagens de log usam
janelas moveis de 30 minutos que terminam durante esse intervalo; por isso elas
podem mudar entre coletas. As metricas de CPU, memoria e paginacao do host acima
vieram de uma coleta separada e nao fazem parte do JSON Docker. A observacao das
tarefas agendadas ocorreu as 07:22, antes desta coleta Docker.

Os artifacts usam aliases estaveis para caminhos e nao armazenam hostname,
username, variaveis de ambiente nem linhas brutas de log; so metadados
estruturais e contagens de assinaturas conhecidas. A evidencia anterior das
07:00 foi substituida porque continha hostname e caminhos locais absolutos.

## Rollback da contencao

Se algum dos projetos parados precisar ser reativado antes da recriacao
canonica, restaurar explicitamente a policy desejada e iniciar somente os
containers necessarios. Nao reativar `reqsys-test-frontend-1` enquanto
`frontend/package.json` estiver ausente.
