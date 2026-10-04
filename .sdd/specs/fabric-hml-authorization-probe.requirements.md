# Probe read-only da autorização Fabric HML — Requisitos

## Contexto

Antes de habilitar o fluxo HML de ponta a ponta é preciso saber, com evidência,
se a service principal `ReqSys ALM Pipeline` já possui autorização suficiente no
workspace `ReqSys - Observabilidade` e se o tenant permite APIs Fabric para
service principals. O probe responde a essa pergunta sem alterar nada.

É um artefato descartável: o script carrega o sufixo `_temp` e o job só executa
na branch efêmera `probe/fabric-hml-authorization-20260921`.

## Requisito 1 — arquivo próprio

O probe vive em `.github/workflows/fabric-hml-authorization-probe.yml`. Ele não
pode substituir nem alterar o workflow canônico
`.github/workflows/fabric-hml-noteri-discovery.yml`, que mantém seu próprio
contrato — inclusive o guard `refs/heads/main` da aplicação de variáveis não
sensíveis.

## Requisito 2 — escopo restrito

O job executa somente quando `github.head_ref` é a branch efêmera do probe, em
runner self-hosted Noteri, com `permissions: contents: read` e checkout do SHA
imutável do HEAD da PR.

## Requisito 3 — somente leitura

O script consulta Azure CLI e APIs Fabric apenas por GET. Não cria, altera nem
remove aplicação, service principal, credencial, role assignment ou tenant
setting.

## Requisito 4 — evidência sanitizada

A execução publica `artifacts/fabric-hml-authorization-probe/evidence.json` com
contagens e status. Valores de segredo e identificadores sensíveis não são
gravados: a evidência registra `secret_value_exposed` e `identifiers_exposed`
como falso.

## Critérios de aceite (Acceptance Criteria)

1. O probe possui workflow próprio e o discovery canônico permanece idêntico ao
   de `main`.
2. O job só dispara na branch `probe/fabric-hml-authorization-20260921`.
3. O checkout usa `github.event.pull_request.head.sha`, não um ref móvel.
4. As permissões do workflow são somente `contents: read`.
5. O script não contém operação de escrita (POST/PUT/PATCH/DELETE) nem flag de
   aplicação.
6. O upload da evidência falha explicitamente quando o arquivo não existe
   (`if-no-files-found: error`).
7. A evidência declara ausência de exposição de segredo e de identificadores.
8. A PR permanece sem merge, deploy e produção.

## Execução efêmera 2026-09-22

Reexecução autorizada para diagnosticar o bloqueio do Report Factory após o
preflight OIDC comprovar token Fabric válido com zero workspaces visíveis.
Esta seção existe apenas para produzir um novo SHA do probe; a PR correspondente
deve permanecer draft, não ser mergeada e ser encerrada após a captura da evidência.
