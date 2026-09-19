# Codex PC24x7 Supervisor — requisitos

## Objetivo
Manter o caminho local `ReqSys → ollama_gateway → Ollama` disponível no Desktop PC24x7 sem depender de uma sessão manual.

## Requisitos
1. O supervisor opera somente em `DESKTOP-PDQK954`, Windows e ambiente local/DEV.
2. Ollama, gateway e backend devem escutar somente em loopback nas portas `11434`, `8008` e `8000`.
3. O provider deve ser lido de `HKCU\Environment`; não copiar valores de segredo para Git, logs ou metadata.
4. O modelo primário é o já configurado no perfil e o fallback local permanece explícito.
5. O supervisor só pode encerrar/reiniciar processos iniciados pela própria instância; porta ocupada por processo não reconhecido falha fechada.
6. O smoke deve autenticar com identidade demo sintética apenas no backend local, chamar `/v1/codex/analyze` com `publicar_no_reqsys=false` e provar resposta real.
7. O gateway deve registrar `requested_model`, modelo efetivo e `fallback_used`.
8. A instalação deve preferir Task Scheduler `ONSTART` sem senha. Falha de permissão pode cair para `HKCU Run`, mas esse estado deve ser explicitamente `requires_user_logon=true` e não pode ser chamado de headless 24x7.
9. Estado, logs e evidência ficam em `%LOCALAPPDATA%\ReqSys\CodexSupervisor`.
10. O release instalado é imutável e identificado pelo SHA de origem.
11. O pós-reboot deve comparar boot epoch e só aprovar quando houver reboot real, runtime saudável, persistência AtStartup e smoke posterior.
12. Nenhum deploy, produção, segredo ou promoção de ambiente integra este incremento.

## Critérios de aceite
- testes unitários do supervisor verdes;
- ciclo físico no Desktop comprova 11434/8008/8000 + smoke ReqSys→IA;
- recuperação de componentes é observável por health/restart count;
- persistência instalada e classificada corretamente;
- `READY_FOR_PR=passed` no HEAD exato;
- E2E pós-reboot permanece pendente até reboot real e `postboot-check --require-reboot` verde.
