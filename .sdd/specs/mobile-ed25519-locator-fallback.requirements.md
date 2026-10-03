# Locator Ed25519 compatível com navegador móvel

## Objetivo

Permitir que Safari e WebViews sem Ed25519 no Web Crypto verifiquem o locator público sem reduzir o controle criptográfico.

## Critérios de aceite

- Web Crypto continua sendo o caminho primário.
- Falha de suporte ao algoritmo usa uma implementação Ed25519 local e auditada.
- Assinaturas inválidas, expiradas ou de origem não permitida continuam rejeitadas.
- Nenhuma chave privada, token ou segredo é adicionado ao frontend.
- O login Microsoft aparece no viewport móvel quando a API está saudável.
