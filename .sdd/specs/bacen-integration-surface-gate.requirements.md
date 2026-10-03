# BACEN Integration Surface Gate

## Objetivo

Adicionar um gate determinístico, sem rede e sem custo adicional, que represente apenas as superfícies BACEN realmente consumidas pelo ReqSys.

O gate deve manter SGS/CDI como superfície ativa no estado atual e impedir que DICT, API Pix ou Open Finance passem a ser consumidos por código executável sem contrato versionado, referência oficial e teste de contrato declarados.

## Requisitos

1. O manifesto canônico deve declarar `sgs_cdi` como `active`.
2. O contrato atual de SGS/CDI deve apontar para a série 12 do SGS e exigir os campos `data` e `valor`.
3. A persistência atual de CDI deve continuar idempotente por `reference_date + source`.
4. DICT, Pix e Open Finance devem permanecer `dormant` enquanto não houver consumidor executável.
5. O gate deve varrer apenas raízes executáveis declaradas e ignorar documentação.
6. Se um marcador de consumidor DICT, Pix ou Open Finance aparecer enquanto a superfície estiver `dormant`, a validação deve falhar fechada.
7. Para ativar uma superfície, devem existir `contract_version`, `official_reference`, `consumer_paths` e `contract_tests`, e os caminhos declarados devem existir.
8. A mesma árvore de código e o mesmo manifesto devem produzir a mesma decisão e o mesmo hash de entrada.
9. O `Pre-PR Readiness` deve executar o gate em todo diff real antes da abertura de PR.
10. O gate não deve realizar chamada de rede, deploy, alteração de segredo, permissão ou produção.

## Critérios de aceite

- O repositório atual retorna `valid`, com `sgs_cdi=active` e DICT/Pix/Open Finance sem detecções.
- Um arquivo executável `pix_client.py` inserido em fixture temporária enquanto `pix=dormant` retorna `invalid`.
- A mesma fixture passa quando `pix` é explicitamente ativado com contrato, referência, consumidor e teste existentes.
- Repetir a validação com a mesma entrada produz resultado idêntico.
- O `Pre-PR Readiness` contém o check `bacen:integration-surfaces`.
- `READY_FOR_PR=passed` deve pertencer ao HEAD exato da branch e `behind_by=0` antes da abertura do PR.
