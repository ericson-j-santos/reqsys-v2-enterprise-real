# Noteri — reparo da referência Python do supervisor

## Objetivo

Corrigir a dependência ausente comprovada no início do supervisor, sem reinstalar o runtime e sem modificar o Python do outro aplicativo.

## Critérios de aceite

- Executar somente em Noteri/DEV pelo Session Launcher e Command Gateway, com fonte e runtime fixados por SHA.
- Confirmar o hash do Startup existente e a falha real `No Python at`, código 103, antes do reparo.
- Preparar CPython oficial 3.12.10 em diretório permanente do runtime, pinado pelo SHA-256 do ZIP. A integridade deve ser comparada novamente ao ZIP pinado, não somente a manifesto local autoafirmado.
- Validar a versão e importar os módulos existentes com `--help` antes de mudar a referência.
- Preservar exatamente os demais bytes do Startup, manter backup e rollback condicionado ao hash, e preservar os arquivos de configuração/versionamento.
- Repetir sem baixar/reinstalar ou gerar outra alteração; rejeitar hashes, paths, links e mudanças concorrentes inválidos.
- Não iniciar/parar supervisor ou worker, registrar tarefa, elevar privilégios, reiniciar o Windows ou alterar o perfil nesta ação.

## Evidência e limites

Registrar SHA, correlação, hashes anterior/posterior e estado de idempotência. O aceite desta ação é a referência Python funcional; heartbeat, recuperação de processo, persistência após login e NORMAL → ESTUDO → replay → NORMAL permanecem validações distintas. Manter o estado parcial até esses testes reais.
