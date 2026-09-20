# OBS-P1 — Observabilidade STG/PROD com alerta governado

## Estado evidenciado

A stack DEV de observabilidade já possui API, Collector, Prometheus, Alertmanager e Grafana como código. Este incremento prepara a expansão governada para STG e PROD sem executar deploy físico, sem publicar portas públicas e sem versionar segredos.

## Escopo deste incremento

- adicionar `compose.observability.stg.yml`;
- adicionar `compose.observability.prod.yml`;
- separar configuração Prometheus por ambiente;
- separar configuração Alertmanager por ambiente;
- exigir endpoint OTLP e senha Grafana por variável externa;
- manter portas publicadas apenas em `127.0.0.1`;
- validar contrato com testes negativos contra falso positivo e vazamento de segredo.

## Fora do escopo

- deploy físico em STG ou PROD;
- promoção de produção;
- criação de segredo;
- configuração real de webhook Teams;
- abertura de portas públicas;
- alteração de DNS, proxy, firewall ou RBAC.

## Critério para sair de pendente

A rota de notificação real só pode ser marcada como validada quando houver, no mesmo `head_sha`:

1. segredo cadastrado em cofre ou mecanismo equivalente;
2. execução autorizada em ambiente alvo;
3. alerta sintético controlado ativo;
4. mensagem recebida no canal controlado com `correlation_id`;
5. restauração do serviço;
6. alerta resolvido no Alertmanager;
7. artifact imutável com ambiente, SHA, run, horários e evidências.

## Controles contra falso positivo

- STG/PROD usam receivers `*-notification-pending` enquanto não houver notificação real;
- testes bloqueiam `webhook_url`, `hooks.office.com`, `bearer`, `token`, `password:` e `api_key` versionados;
- testes bloqueiam portas não locais;
- testes exigem labels `environment` distintas;
- testes exigem volumes segregados por ambiente.

## Próximo incremento

Executar a menor validação STG autorizada, com segredo aprovado fora do repositório e artifact de alerta ativo/resolvido. PROD permanece bloqueado até STG evidenciado.
