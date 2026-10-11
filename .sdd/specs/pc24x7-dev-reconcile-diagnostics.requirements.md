# Diagnóstico restrito da reconciliação PC24x7 DEV

## Objetivo
Eliminar a ambiguidade dos erros de reconciliação da issue #1532 sem expor
credenciais e fornecer uma leitura mínima do runtime DEV antes de autorizar recuperação.

## Requisitos
1. O loader do modo Study deve tratar ImportError e ModuleNotFoundError na execução direta.
2. Falhas Compose sensíveis devem identificar somente fase allowlisted, categoria e exit code.
   stdout, stderr, argumentos e mensagens de exceções externas não podem compor a evidência.
3. O diagnóstico deve exigir DEV, host PC24x7 exato, daemon Docker Desktop Linux local
   e identidade permitida descoberta pela porta DEV 8210. DOCKER_HOST/DOCKER_CONTEXT
   e contextos remotos devem bloquear antes de consultar qualquer daemon.
4. A coleta limita-se a ps e inspect com formato fixo dos serviços api/frontend/nginx.
   Não coletar Config.Env, logs, credenciais ou health log; não executar build/up/restart/rm.
5. Projetos desconhecidos, PROD, inventário ambíguo, troca/desaparecimento da API
   e metadados inválidos devem falhar fechado.
6. O modo explícito --stdout-only deve emitir JSON completo sem escrever arquivo,
   preservando o estado do worktree e os códigos de saída; execução governada usa -B.
   O modo alternativo --output exige contrato de escrita e só permite evidência JSON
   nova sob artifacts/pc24x7-dev-diagnostic. Sobrescrita, escape do diretório, symlink
   e reparse point devem ser recusados. Exigir exatamente um dos dois modos.
7. Metadados coletados não comprovam runtime saudável, SHA implantado ou E2E Teams.

## Critérios de aceite
- Testes isolados cobrem os requisitos positivos e negativos, sem Docker ou Teams externo.
- READY_FOR_PR pertence ao HEAD publicado antes de abrir PR.
- Diagnóstico físico e replay Teams permanecem pendentes de execução autorizada em DEV.


