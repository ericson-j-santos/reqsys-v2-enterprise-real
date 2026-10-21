# Recuperação de notificações baseada em prova

## Problema e escopo
Na main 971a939b93f38fed147d37bf0c096527a0928b78, o observador encerra
incidentes quando o workflow conclui success, mesmo que o envio seja suprimido.
A execução 39574202403 exemplifica no_material_remediation com success.

## Critérios de aceite
1. Success informa somente workflow_succeeded. Sem leitor independente, healthy e
   delivery_verified permanecem false; delivery_state=unverified.
2. Workflow manual é diagnóstico; schedule é locator_watch, nunca prova de entrega.
3. Falha continua abrindo/atualizando o incidente; skipped/cancelled não recuperam.
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
