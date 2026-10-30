# Recuperação de notificações baseada em prova

## Problema e escopo
Na main 971a939b93f38fed147d37bf0c096527a0928b78, o observador encerra
incidentes quando o workflow conclui success, mesmo que o envio seja suprimido.
A execução 39574202403 exemplifica no_material_remediation com success.

## Critérios de aceite
1. Success informa somente workflow_succeeded. Sem leitor independente, healthy e
   delivery_verified permanecem false; delivery_state=unverified.
2. Workflow manual é diagnóstico; schedule é locator_watch, nunca prova de entrega.
3. Falha de evento de entrega (`push` ou `workflow_run`) continua abrindo/atualizando o incidente. Falha de `schedule` pertence ao monitor do locator e não abre incidente de entrega; skipped/cancelled não recuperam.
4. Nenhum incidente é fechado automaticamente sem prova independente no destino.
5. Replay mantém a decisão sem envio adicional. Controle negativo deve reproduzir
   a expressão antiga e demonstrar que seria rejeitada.
6. Autenticação, assinatura, TTL de 900s e custo adicional zero são preservados.
7. Teste usa o bloco Python real do workflow e integra o Pre-PR Readiness via SDD.

## Limites
Esta correção não renova locator nem publica Pages. O produtor do dashboard já
gera artefato; o publicador canônico continua manual e exige autorização de
publicação. Não ampliar TTL, trocar chave ou inventar runtime.
Entrega ponta a ponta exige leitura independente no Teams vinculada ao envio.
A evidência de aceite do webhook, isoladamente, não é comprovação de entrega.

## Evidência adicional de 30/10/2026
O run 41061343405 falhou no gate de frescor do locator; o job de envio ao Teams
ficou skipped. O observador comentou na issue #3063 como se fosse falha de
entrega. O filtro de evento impede esse alerta incorreto e conserva falhas de
execuções de entrega para triagem.
