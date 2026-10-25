# WSL → PowerShell governado

Esta ponte resolve chamadas locais do WSL para o Windows sem expor um shell
administrativo genérico. Cada operação é um script PowerShell versionado com
argumentos exatos na política.

## Diagnóstico

Na raiz do repositório dentro do WSL:

```bash
python3 scripts/wsl_powershell_bridge.py probe
```

O resultado esperado contém `"status": "ready"` e o caminho do
`powershell.exe`.

## Ativar o Desktop Admin Broker

```bash
python3 scripts/wsl_powershell_bridge.py run \
  --script scripts/activate_desktop_admin_broker_from_wsl.ps1 \
  --timeout-seconds 180 \
  -- \
  -Confirm ACTIVATE-REQSYS-DESKTOP-ADMIN-BROKER
```

O Windows apresentará UAC uma única vez. Selecione **Sim**. O comando só
termina com sucesso após comprovar:

- tarefa `\Automation\ReqSysDesktopAdminBroker`;
- trigger `AtStartup`;
- identidade `S4U`;
- run level `Highest`;
- tarefa habilitada;
- Python e `pywin32` funcionais.

A metadata não é mais vinculada ao `LOCALAPPDATA` do usuário que abriu o
PowerShell. O ativador examina os perfis locais e aceita somente uma instalação
com contrato íntegro para `DESKTOP-PDQK954`.

## Evidência

A ponte grava JSON em
`~/.local/state/reqsys/wsl-powershell-bridge/`. O arquivo contém SHA-256 e
tamanho de stdout/stderr, mas não o conteúdo, tokens ou credenciais.

## Adicionar nova operação

1. Criar um `.ps1` autocontido e fail-closed em `scripts/`.
2. Adicionar o caminho e os argumentos exatos à política.
3. Declarar ambiente `local/DEV`.
4. Adicionar testes positivos, negativos e de ausência de shell arbitrário.
5. Executar Pre-PR Readiness e integrar por revisão.

Não amplie a política para diretórios inteiros, `-Command`, comandos
codificados ou argumentos livres. Operações administrativas devem usar o
Desktop Admin Broker depois da ativação inicial.
