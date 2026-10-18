# Requisitos — GitLab Gitleaks sanitized evidence

## Contexto

A pipeline GitLab `2960078371` no SHA canônico `10051c1e` comprovou todos os
scanners verdes exceto `secret_detection_gitleaks`, que encontrou 5 achados.
O artifact bruto existe, mas o conector operacional disponível não expõe seu
conteúdo. Copiar `Secret`, `Match` ou conteúdo capturado para logs/issue seria
incompatível com a política de segurança.

## Critérios de aceite

1. O job Gitleaks original permanece bloqueante, com `--redact` e `--exit-code 1`.
2. Um job separado executa `when: always`, depende do artifact do Gitleaks e não
   altera o resultado do scanner original.
3. O resumo permite somente `RuleID`, `File`, `StartLine` e `EndLine`.
4. `Secret`, `Match`, `Entropy`, `Fingerprint`, commit, autor, email,
   mensagem e demais campos não podem aparecer no resumo nem nas linhas de log.
5. Caminhos absolutos, traversal e caracteres de controle são rejeitados para
   evitar vazamento/log injection.
6. A saída é determinística e ordenada.
7. O job sanitizador é `allow_failure: true`; falha dele nunca converte um
   Gitleaks vermelho em verde.
8. O artifact bruto continua preservado conforme a retenção atual; o resumo
   sanitizado é publicado separadamente.
9. Testes cobrem segredo sentinela, ordenação, inputs inválidos e contrato YAML.
10. Após integração e mirror, uma pipeline real deve produzir as 5 entradas
    sanitizadas; só então corrigir as causas/fixtures específicas sem allowlist ampla.
