# Ponte governada WSL → Windows PowerShell

## Objetivo

Disponibilizar transporte local, previsível e auditável para que o WSL execute
scripts PowerShell versionados no Windows, inclusive o ativador inicial do
Desktop Admin Broker, sem criar um shell administrativo arbitrário.

## Classificação

`gap_fix`.

## Requisitos

1. A ponte deve executar apenas dentro do WSL com Windows Interop disponível.
2. O executável aceito é o Windows PowerShell nativo localizado no Windows.
3. O transporte deve usar vetor de argumentos e nunca `shell=True`,
   `eval`, `Invoke-Expression`, `-Command` fornecido pelo usuário ou
   `-EncodedCommand`.
4. Somente scripts `.ps1` versionados dentro do repositório e exatamente
   allowlisted em `config/wsl-powershell-bridge.policy.json` podem executar.
5. Os argumentos devem corresponder exatamente aos argumentos da política.
6. Toda entrada deve permanecer limitada a local/DEV; HML, STG e PROD são
   proibidos.
7. O timeout deve ser positivo e limitado pela política.
8. Variáveis de ambiente com nomes associados a segredo, credencial, token,
   senha ou chave, além de `WSLENV`, não devem atravessar a fronteira.
9. Evidência local deve registrar apenas metadados e hashes de stdout/stderr,
   nunca o conteúdo.
10. Elevação não deve ser silenciosa. Scripts administrativos devem declarar
    `interactive_uac=true` e depender do consentimento UAC local.
11. O ativador do Admin Broker deve localizar metadata válida entre os perfis
    Windows, validar host, release, launcher, Python e pywin32 antes da elevação.
12. O ativador deve aceitar somente
    `ACTIVATE-REQSYS-DESKTOP-ADMIN-BROKER`.
13. O sucesso exige readback independente da tarefa
    `\Automation\ReqSysDesktopAdminBroker` com
    `AtStartup + S4U + highest + enabled`.
14. A solução não pode abrir listener, WinRM, SSH, SMB ou WMI remoto, nem
    fornecer comando administrativo arbitrário.
15. Nenhum reboot, deploy, segredo ou ambiente produtivo pode ser tocado.

## Critérios de aceite

- testes unitários positivos e negativos verdes;
- compilação Python verde;
- política e argumentos exatos comprovados;
- tentativa de script fora do repositório, extensão não PowerShell, argumento
  divergente, timeout excessivo ou ambiente não DEV falha fechada;
- o ativador comprova Python/pywin32 e o contrato integral da tarefa;
- Pre-PR Readiness no SHA exato produz `READY_FOR_PR=passed`.
