# Site ReqSys — validação física sem execução remota

## Objetivo
Versionar o painel local em português brasileiro para acompanhar, com honestidade de evidências, a validação física entre DESKTOP-PDQK954, DESKTOP-RP23OGS e Noteri. O frontend não substitui a telemetria autenticada do Runtime Platform, a fonte canônica TODO Global, os operadores autorizados ou o Command Gateway.

## Requisitos
- Proteger `main`: alterações apenas em `tools/reqsys-validacao-fisica/**` e na especificação `.sdd/specs/reqsys-validacao-fisica.*`, sem sobrescrever código existente.
- Exibir fila Pareto, três hosts e dez etapas obrigatórias com peso igual (um critério físico por etapa); sem prova externa autenticada, aceite físico `0/10`, host comprovado `0/3` e prazo não estimável.
- Registrar relatos, logs, SHA, evidência antes/depois, continuidade, rollback e exportação local, sempre separados de prova independente.
- Nunca executar comandos, dispatch, reboot, push, merge, deploy, mudança administrativa ou leitura de segredo a partir da página.
- Confirmar explicitamente cada alteração dos dados locais, rejeitar SHA inválido e importações incompatíveis; preservar controles contra repetição e falso positivo.
- Tratar importações JSON como dados não confiáveis; construir somente tags e atributos autorizados no DOM, recusar URL, HTML ativo, eventos inline, scripts e tags externas.
- Preservar acessibilidade, responsividade, LGPD, limite de custo adicional R$ 0,00, sem Docker.
- Admitir integração com evidências reais somente no futuro mediante adaptador autenticado somente leitura, trilha de auditoria, controle de acesso e provas de ambiente, host, sessão, lease, run e SHA. Esta entrega não implementa nem comprova esse adaptador.

## Critérios de aceite (Acceptance Criteria)
1. Frontend, CSS, JavaScript, documentação e testes estão versionados em branch isolada, com readback de bytes e SHA; `main` não é alterada.
2. JavaScript passa na verificação de sintaxe e nos testes lógicos locais; Chromium confirma navegação das sete visões.
3. Testes positivos e negativos comprovam que SHA inválido, cancelamento e importação maliciosa não criam mudanças ou executam HTML ativo.
4. A edição local de todos os requisitos de host **não** muda seu estado autenticado para pronto.
5. Registro de tarefa, pickup, checkpoint ou E2E sem testemunho externo **não** altera `0/10` de aceite comprovado.
6. Exportação JSON e Markdown ocorre localmente, sem envio automático de dados.
7. `scripts/sdd_gate.py` encontra a especificação e os testes mapeados no SHA de publicação.
8. O scanner de segurança não detecta construção ativa de HTML com entradas não confiáveis; não desligar nenhum gate e comprovar no CI atual.
9. A PR só pode ser aberta quando `READY_FOR_PR=passed` for comprovado na base atual; merge e deploy exigem autorização e gates separados.
10. O E2E real entre hosts fica bloqueado até preflight, Gateway, session, worktree, lease, checkpoint e validadores independentes autenticados, sem considerar CI ou este site como homologação física.

## Evidência e limites
Issue #3147. Regras principais: `chatgpt-operational-rules` 1.6.21, SHA `58dcd4200f412a866278027ba9e433439a03f3b3`. Linha de base ReqSys `a05e64bbc58a15314b42cfa9314f1d415535b05b`. A publicação desta interface não equivale a implantação no servidor, sincronização do TODO Global ou operação entre computadores.
