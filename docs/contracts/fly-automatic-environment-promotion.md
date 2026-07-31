# Fly Automatic Environment Promotion

## Objetivo

Promover o mesmo SHA imutável da `main` em sequência `DEV → STG → PROD`, usando evidências coletadas antes e depois de cada estágio.

## Gatilhos

- conclusão bem-sucedida do `Post-merge Main Runtime Validator` em `push` da `main`;
- reconciliação horária;
- execução manual governada.

## Contratos de evidência

Cada ambiente produz e correlaciona:

- estado sanitizado dos apps Fly;
- máquinas e regiões ativas;
- configuração crítica local e remota;
- nomes e estado de implantação dos secrets obrigatórios, nunca seus valores;
- release e checks do Fly;
- smoke dos endpoints públicos;
- readiness da API e runtime;
- SHA publicado;
- validação de login e redirect Azure.

A decisão é `promotion_stage_ready` apenas quando todos os contratos estão íntegros, o ambiente é o esperado, o SHA observado coincide com o SHA alvo e não existem bloqueios.

## Fluxo

1. Resolver o SHA atual da `main`.
2. Rejeitar execução obsoleta quando a `main` avançar.
3. Capturar DEV.
4. Implantar DEV apenas se houver drift e validar novamente em modo estrito.
5. Repetir a mesma política para STG somente após DEV verde.
6. Consultar o BACEN Production Hard Gate.
7. Capturar PROD.
8. Implantar PROD somente quando houver drift, STG estiver verde e o gate BACEN autorizar.
9. Validar PROD novamente em modo estrito.
10. Publicar relatório imutável de toda a cadeia.

## Guard rails

- fail-closed para artifact ausente, JSON inválido, command failure, secret ausente, check degradado, login inválido ou SHA divergente;
- nenhuma persistência de valores de secrets;
- nenhum bypass do ambiente GitHub ou do BACEN Production Hard Gate;
- somente o SHA atual da `main` pode ser implantado;
- estágios sequenciais e sem paralelismo entre ambientes;
- produção pode permanecer bloqueada sem transformar a decisão regulatória em aprovação automática;
- artifacts de ambiente retidos por 90 dias e resumo da cadeia por 365 dias.

## Rollback

O workflow não executa rollback destrutivo automático. Uma falha interrompe a cadeia no estágio atual e preserva os artifacts para diagnóstico. O rollback operacional deve reutilizar um SHA anterior autorizado por um fluxo específico de rollback, sujeito aos mesmos gates.
