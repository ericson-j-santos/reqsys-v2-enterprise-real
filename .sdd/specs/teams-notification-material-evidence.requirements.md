# Teams Notification — critérios materiais de envio e recuperação

## Objetivo

Impedir mensagens de triagem para execuções puladas/canceladas ou sem artefato material válido e impedir fechamento de incidente por mera conclusão verde do workflow notificador.

## Requisitos

1. `Ollama CI Triage` só é notificável quando a origem conclui `success` e o artefato contém PR positivo, análise material, SHA completo e resultado não vazio.
2. Artefato ausente, inválido ou identidade `n/a` deve suprimir a notificação com motivo sanitizado.
3. `PR CI Remediation` deve continuar suprimindo `reruns_executed <= 0`.
4. Cada run do notificador deve expor exatamente um marcador de job bem-sucedido: entrega real ou supressão sem mudança material.
5. O observador deve consultar a API oficial de jobs e só considerar recuperação quando run ID, HEAD SHA, nome do job e marcador de entrega real coincidirem.
6. `success` genérico, supressão normal ou resposta sem identidade coincidente nunca fecha incidente; supressão normal também não abre incidente.
7. O incremento não altera permissões, destinatários, plataforma, secrets nem envia mensagem real de teste.
8. O notificador não cria artefato intermediário adicional; permanece apenas a evidência operacional sanitizada do observador.
9. Resultado de entrega é validado por rota: gateway exige `entregue is true`; contingência exige `success is true`, rota `webhook` e HTTP 2xx. Valores textuais ou campos genéricos não confirmam entrega.
10. Somente motivos explicitamente permitidos são `material_noop`; falha de schema, identidade ou SHA interrompe o notificador como `evidence_failure`.
11. Timeout, erro da API, JSON inválido ou paginação incompleta produz `observation_unavailable`, registrado separadamente sem afirmar falha de entrega e sem fechar incidente.

## Aceite

- Testes positivos e negativos cobrem artefato ausente/inválido, identidade de SHA/run divergente, origem skipped/cancelled, remediação sem ação, supressão normal e entrega real.
- Workflows e SDD passam nos validadores existentes.
- Recuperação real continua dependendo de nova evidência pós-integração; este incremento não comprova entrega E2E.
