# Requisitos — E2E com Ollama Gateway já ativo

## Objetivo
Permitir que o E2E físico do Codex/ReqSys reutilize explicitamente um `reqsys-ollama-local-gateway` já ativo em DEV/test, sem derrubar serviço existente e mantendo o backend temporário ligado ao SHA sob validação.

## Requisitos
1. O modo padrão continua exigindo porta do gateway livre e sobe um gateway temporário.
2. `--reuse-running-gateway` só aceita health com `status=ok`, serviço canônico, ambiente DEV/test e `auth_required=false`.
3. O backend temporário usa porta configurável por `--backend-port` e continua sendo iniciado a partir do SHA validado.
4. `--gateway-port` e `--backend-port` devem ser válidos e diferentes.
5. O controle negativo de fallback deve continuar exigindo `fallback_used=true` e o modelo local configurado.
6. O E2E continua sem deploy, produção ou leitura de segredos.
7. Um gateway reutilizado não pode ser encerrado pelo cleanup do E2E.

## Critérios de aceite
- testes unitários cobrem health válido, serviço incorreto, produção, autenticação obrigatória, porta e URL configurável;
- E2E físico executa contra gateway DEV já ativo e backend temporário do SHA corrente;
- replay do E2E não derruba nem substitui o gateway preexistente.
