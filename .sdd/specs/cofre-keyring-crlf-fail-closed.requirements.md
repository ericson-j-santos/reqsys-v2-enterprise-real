# Cofre — compatibilidade CRLF e gravação fail-closed

## Objetivo

Preservar a compatibilidade de leitura do Cofre com arquivos legados cifrados usando passphrase derivada de arquivo CRLF, sem permitir que falhas de descriptografia provoquem sobrescrita silenciosa do arquivo existente.

## Requisitos

1. A leitura deve aceitar a passphrase canônica e, como único fallback legado, a variante com um CR terminal.
2. Novas gravações devem usar sempre a forma canônica da passphrase, sem CR terminal introduzido por CRLF.
3. Um arquivo existente que não possa ser descriptografado deve bloquear `set_password`; não pode ser tratado como Cofre vazio.
4. Quando a gravação for bloqueada por falha de descriptografia, os bytes do arquivo existente devem permanecer inalterados.
5. A primeira gravação bem-sucedida sobre um Cofre legado CRLF deve migrar o conteúdo para a forma canônica preservando as entradas existentes.
6. O incremento não deve registrar segredos reais nem alterar deploy, runtime, permissões ou ambientes.

## Critérios de aceite

1. `backend/tests/test_keyring_backend.py` comprova leitura do legado CRLF quando o runtime fornece a passphrase com e sem CR terminal.
2. O teste de migração comprova que a primeira escrita subsequente pode ser descriptografada com a passphrase canônica e preserva dados anteriores.
3. O teste fail-closed comprova que `InvalidTag` é propagado em gravação sobre arquivo incompatível/corrompido e que o conteúdo permanece byte-for-byte inalterado.
4. Os testes existentes de round-trip, persistência, remoção e ausência de passphrase permanecem aprovados.
5. O SDD gate reconhece esta especificação no mesmo SHA da mudança funcional.
