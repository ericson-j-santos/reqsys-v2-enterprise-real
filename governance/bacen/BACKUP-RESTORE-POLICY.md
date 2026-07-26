# Política de Backup, Restauração e Continuidade — ReqSys

## Objetivo

Garantir recuperação verificável dos dados, configurações e artefatos críticos do ReqSys, com evidência auditável de execução, integridade e restauração.

## Escopo

- bancos de dados e filas persistentes;
- configurações versionadas e infraestrutura como código;
- artifacts de governança e evidências regulatórias;
- ambientes STG e PROD;
- integrações críticas e segredos gerenciados pelo provedor.

## Requisitos mínimos

1. Backups devem ser automatizados, criptografados, inventariados e associados ao ambiente e ao ativo de origem.
2. Cada execução deve registrar `correlation_id`, timestamp UTC, commit SHA quando aplicável, identificador do backup e digest SHA-256.
3. Restaurações devem ser testadas em ambiente isolado, sem sobrescrever dados produtivos.
4. O teste deve validar integridade, disponibilidade do conteúdo restaurado e cumprimento do RPO/RTO definidos.
5. Falhas devem abrir incidente operacional e bloquear a promoção de produção quando afetarem ativo crítico.
6. Evidências devem ser retidas por no mínimo 365 dias ou pelo prazo corporativo superior aplicável.
7. O acesso a backups deve seguir menor privilégio, segregação de função e trilha individual.

## Objetivos operacionais iniciais

| Classe | RPO máximo | RTO máximo | Frequência de teste |
|---|---:|---:|---:|
| Dados críticos PROD | 24 horas | 4 horas | Trimestral |
| Configuração e IaC | Por alteração | 2 horas | Semestral |
| Evidências regulatórias | 24 horas | 8 horas | Semestral |

## Evidência mínima de restauração

O artifact JSON deve conter:

- `schema_version`;
- `control_id=BACEN-04`;
- `environment`;
- `asset_id`;
- `backup_id`;
- `backup_created_at`;
- `restore_started_at` e `restore_completed_at`;
- `rpo_minutes` e `rto_minutes`;
- `integrity_sha256`;
- `correlation_id`;
- `result`;
- `executed_by` e `reviewed_by`;
- `commit_sha` e `workflow_run_id` quando disponíveis.

## Critérios de bloqueio

- backup ausente ou expirado para ativo crítico;
- restauração não testada no ciclo previsto;
- digest ausente ou divergente;
- RPO/RTO acima do limite sem exceção formal;
- evidência sem responsável, ambiente ou correlação;
- restauração executada diretamente sobre PROD sem procedimento aprovado.

## Responsabilidades

- `RUNTIME_OPERATOR`: executar e manter rotinas e testes;
- `SECURITY`: validar criptografia, acesso e retenção;
- `GOVERNANCE`: revisar exceções, indicadores e evidências;
- proprietário do ativo: aprovar RPO/RTO e criticidade.
