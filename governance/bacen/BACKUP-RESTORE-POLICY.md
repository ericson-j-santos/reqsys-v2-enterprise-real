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
8. A ausência de notificação ou de atualização do dashboard deve falhar o gate operacional fora de pull requests.

## Objetivos operacionais iniciais

| Classe | RPO máximo | RTO máximo | Frequência de teste |
|---|---:|---:|---:|
| Dados críticos PROD | 24 horas | 4 horas | Trimestral |
| Configuração e IaC | Por alteração | 2 horas | Semestral |
| Evidências regulatórias | 24 horas | 8 horas | Semestral |

## Agendamento operacional

- O teste real de backup e restauração PostgreSQL em STG isolado executa automaticamente no primeiro dia de janeiro, abril, julho e outubro, às 06:17 no horário de Brasília.
- Execuções manuais permanecem disponíveis por `workflow_dispatch` para validação extraordinária ou pós-incidente.
- Alterações nos scripts, política, matriz BACEN ou workflow executam o teste no ciclo de PR/push.
- A concorrência é serializada para evitar sobreposição de restaurações e perda de evidência.

## Evidência mínima de restauração

A evidência JSON deve conter:

- `schema_version`;
- `control_id=BACEN-04`;
- `environment`;
- `asset_id`;
- `backup_id`;
- `backup_created_at`;
- `restore_started_at` e `restore_completed_at`;
- `rpo_minutes` e `rpo_target_minutes`;
- `rto_seconds` e `rto_target_seconds`;
- `backup_sha256`;
- `integrity_match` e snapshots de origem/destino;
- `correlation_id`;
- `result`;
- `executed_by` e `reviewed_by` quando aplicáveis;
- `commit_sha` e `workflow_run_id` quando disponíveis;
- confirmação explícita de que produção não foi acessada.

## Retenção e trilha de auditoria

- O artifact operacional do GitHub Actions mantém o JSON bruto, o dashboard JSON, o resumo Markdown, a página HTML e o Adaptive Card pelo limite configurado da plataforma.
- Como a configuração atual do repositório limita artifacts a aproximadamente 90 dias, cada execução também registra um comentário imutável no dashboard central com o dashboard e a evidência JSON completos.
- O histórico de comentários do dashboard central constitui a trilha durável mínima de 365 dias e não deve ser apagado sem aprovação de `GOVERNANCE`.
- O dashboard central é a issue `#1156`, atualizada automaticamente após cada execução não originada de pull request.

## Monitoramento e mensagens de acompanhamento

- O dashboard central deve exibir saúde, resultado, integridade, RPO/RTO medidos e alvos, volume validado, acesso a produção, próxima execução, SHA e `correlation_id`.
- Cada execução não originada de pull request deve enviar Adaptive Card ao Teams usando `TEAMS_WEBHOOK_URL` e `TEAMS_WEBHOOK_RECIPIENT`.
- Ausência de secrets, falha do gateway ou entrega não confirmada deve falhar o gate operacional.
- O cartão deve conter link direto para a execução e os principais indicadores de continuidade.

## Critérios de bloqueio

- backup ausente ou expirado para ativo crítico;
- restauração não testada no ciclo previsto;
- digest ausente ou divergente;
- RPO/RTO acima do limite sem exceção formal;
- evidência sem responsável, ambiente ou correlação;
- restauração executada diretamente sobre PROD sem procedimento aprovado;
- dashboard não gerado ou não atualizado;
- mensagem de acompanhamento não entregue em execução operacional.

## Responsabilidades

- `RUNTIME_OPERATOR`: executar e manter rotinas e testes;
- `SECURITY`: validar criptografia, acesso e retenção;
- `GOVERNANCE`: revisar exceções, indicadores e evidências;
- proprietário do ativo: aprovar RPO/RTO e criticidade.
