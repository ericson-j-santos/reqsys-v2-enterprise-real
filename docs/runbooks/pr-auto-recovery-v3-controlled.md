# PR Auto Recovery Controlled v3

## Objetivo

Preparar abertura automática de PR substituto em draft, somente quando gates explícitos forem atendidos.

## Estado padrão

`default_enabled=false`

A v3 documenta e configura os gates. A execução real deve permanecer desligada até validação em ambiente controlado.

## Fluxo controlado

1. Detectar PR original `mergeable=false`.
2. Validar allowlist e blocklist.
3. Validar limites de tamanho do diff.
4. Criar branch substituta a partir da `main` atual.
5. Reaplicar somente arquivos permitidos.
6. Abrir PR substituto em draft.
7. Comentar no PR original.
8. Aguardar validação humana.

## Proibido

- Merge automático.
- Fechamento automático do PR original.
- Alteração de secrets.
- Alteração de branch protection.
- Deploy.
- Aprovação de environment.

## Critérios para habilitar execução real

- CI verde da v3.
- Runbook aprovado.
- Gates versionados revisados.
- Evidência de dry-run com PR real bloqueado.
- Primeiro uso real limitado a um PR pequeno e docs-only.

## Rollback

Como `default_enabled=false`, rollback operacional é manter a execução real desligada. Para rollback completo, remover workflow/configuração em PR separado.
