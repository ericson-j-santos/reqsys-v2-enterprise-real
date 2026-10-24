# Admissão de notificações Teams antes dos efeitos externos

## Falha e escopo

O workflow_run 39956696535 (job 120424198297) enviou uma mensagem de triagem concluída após um upstream Ollama skipped, sem evidência material. O consumidor também resolvia locator e configurava credenciais antes de identificar remediação sem reruns.

Este hotfix mantém o comportamento de entrega existente apenas para eventos materiais admitidos. Não muda destinatários, credenciais, permissões, fallback, cron do locator, gates ou tratamento do runtime.

## Critérios de aceite

1. O job notify-teams não inicia para upstream skipped, cancelled ou neutral.
2. Preparação/admissão precede todo uso de locator e secrets de entrega; env do job não contém secret.
3. No-op de remediação registra reason=no_material_remediation sem criar payload de entrega.
4. Evidência ausente, versão incorreta, conclusão desconhecida, contador inválido ou efeito não comprovado falha fechado antes do envio.
5. Triagem com evidência OK, DEGRADED ou BLOCKED continua notificável; motivo real preservado.
6. Commits main e notificações manuais continuam usando preparação e entrega canônica, sem alteração de destinatário.
7. Preparação baixa evidência uma única vez; entrega usa o payload já preparado, sem reclassificar após ler credenciais.
8. Os testes executam o Python real embutido da preparação com fixtures sintéticas, incluindo skipped sem chamada de rede e remediação no-op sem payload.
9. Guardrails de redirect sem Authorization, fallback, locator e resultado estrito permanecem intactos.

## Validação e limites

Regressão nativa em tests/test_teams_notification_admission.py, contrato Teams existente e invariantes do locator. Executar no Pre-PR e no workflow Teams Commit Notification Contract para o HEAD exato.

Nenhum teste deve enviar mensagem, ler secret, acessar host, iniciar Docker ou comprovar ACK humano. Publicação ainda depende da janela de bootstrap explicitamente autorizada, devido ao consumidor legado na main. O gate conjunto 39962211237, reference OPS-GAP-TEAMS-NATIVE-CI-BOOTSTRAP, admite este hotfix com a substituição nativa PostgreSQL necessária para validar a PR sem Docker. O gate anterior 39960114802 cobria apenas Teams e não foi reutilizado para ampliar escopo. A decisão de gate não substitui a autorização específica de manutenção, o READY_FOR_PR, os checks nem a revisão.

## Fora de escopo e rollback

Este componente não implementa a migração PostgreSQL/CI, descrita em especificação complementar do mesmo incremento atômico. Recuperação de host, novas credenciais, publicação de produto, alteração de observabilidade e desligamento permanente de notificações permanecem fora do escopo. Reverter somente estes arquivos e restaurar qualquer estado operacional de manutenção separadamente registrado; não reenviar eventos antigos sem classificação e deduplicação.
