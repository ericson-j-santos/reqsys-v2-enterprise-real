# Retomada do supervisor Noteri (DEV)

Pedido autorizado: conferir processos atuais e iniciar somente a instância correta após o reparo Python, preservando a segurança e o perfil atual.

## Critérios de aceite

- Origem com SHA exato, Windows/Noteri e configurações instaladas iguais às medições físicas anteriores.
- Biblioteca de inspeção isolada e verificada contra wheel oficial psutil 7.2.2 Windows x64, SHA-256 eb7e81434c8d223ec4a219b5fc1c47d0417b12be7ea866e24fb5ad6e84b3d988. Não alterar Python global nem Hermes.
- Conferir executável, argumentos, diretório, criação e relação pai/filho. Processo ambíguo, sem acesso ou duplicado bloqueia o start.
- Não encerrar processos a partir de PIDs antigos, nem usar o reinício legado.
- Início serializado, com rechecagem de ausência e confirmação de status novo. Replay não inicia outra instância.
- Reversão do próprio start por shutdown.request somente se a instância criada continuar inequivocamente identificada. Nenhum processo de terceiros pode ser encerrado.
- Preservar byte a byte o perfil atual e configurações. Não alterar privilégios, energia, segurança ou produção.
- A retomada do processo não equivale a homologação: confirmar heartbeat crescente, persistência e E2E da instalação real separadamente.

Testes: tests/test_noteri_supervisor_resume.py. Rastreabilidade: reqsys-engineering-orchestrator issue 16.
