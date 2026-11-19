# Codex Local — Central de Execuções (módulo local)

## Resultado
Site estático, totalmente em português brasileiro, criado como **extensão local de inspeção**. Não cria sistema concorrente ao ReqSys, TODO Global, GitHub ou à central de acompanhamento já publicada. **Versão 1.2:** fluxo guiado com pré-condições e avanço sequencial fail-closed, importação de checkpoint atômica e consulta pública ao GitHub sob demanda (GET). Não executa mutações, publicação nem gastos incrementais. Custo da criação e testes locais: R$ 0,00.

## Como usar
1. Abra `index.html` no navegador moderno (Chrome/Edge/Firefox); não precisa instalar servidor, Docker ou dependências.
2. Abra **Execuções**, clique em **Registrar execução** e informe dados reais da issue canônica (#3126 ou #42), correlação/chave idempotente e demais campos conhecidos. Não invente campos não confirmados.
3. Em **Fluxo guiado**, registre cada transição com evidência. Em **Evidências**, anexe referências, hashes, comandos/respostas sanitizadas e provas de destino. Todas as anotações são locais e **não validam** fatos externos.
4. Abra **Fontes oficiais** e clique **Consultar fontes oficiais**: a tela fará seis GETs públicos ao GitHub para as duas issues existentes e as `main` de quatro repositórios permitidos. Quando houver `run_id` real na ficha, clique **Conferir run informado** para consultar apenas aquele run, seus jobs e metadados dos artefatos (até 30 jobs/10 artefatos). Não há busca por execuções fictícias.
5. Clique **Exportar checkpoint**, guarde o JSON fora do dispositivo e reimporte no destino. O JSON inclui `digest_sha256` para conferir integridade de registros **locais**; conflito ou hash divergente bloqueia a importação. As leituras do GitHub não são escritas nesse checkpoint.
6. Em **Fluxo guiado**, conclua uma etapa por vez. A interface informa a próxima etapa e os campos em falta. Não aceita concluir etapa 12 com requisitos/custo/SHA/lease/modelo/checkpoint/Validator/replay/autorizações pendentes; a conclusão local chama-se **encerramento documental**, sem homologação do runtime.
7. Confirme estado real e execução ponta a ponta nos sistemas canônicos. Não considere a UI uma prova automática.

## Segurança e limites
- O site não tem dependências de bibliotecas externas, backend, telemetria, credenciais ou scripts remotos. A única conexão de rede autorizada é `https://api.github.com` em chamadas GET explicitamente iniciadas pelo usuário. API pública sujeita a CORS e limite de acesso. Sem login e sem chamadas aos endpoints privados do ReqSys/hosts.
- O código restringe rotas a issues numéricas, `branches/main` e runs/jobs/artefatos dos quatro repositórios definidos na aplicação. Credenciais são omitidas, redirecionamentos e respostas inconsistentes são rejeitados. Em erros de rede/API/rate limit, o dado permanece **não confirmado**.
- Metadados de GitHub: existência/status de issue, SHA da branch, status de run, runner indicado em job e nome de artefato. Essas informações não certificam integridade física de checkpoint, modelo/digest Ollama, posse de lease, saúde do Gateway ou efeito no ReqSys.
- As respostas da API são mostradas como texto e mantidas só na memória da aba; nunca são escritas automaticamente no registro ou no JSON. Não usar como substituto de readback autenticado do runtime.
- `sessionStorage` evita perder o rascunho ao recarregar a mesma aba, mas **não garante durabilidade, segurança de dados pessoais nem compartilhamento**. Exporte o JSON para preservar o registro.
- Entradas que aparentam conter tokens, segredos, cabeçalhos Authorization, e-mails e CPF são recusadas. Filtro textual é apenas defesa em profundidade: não cole material sensível.
- O SHA-256 é a verificação de integridade **do JSON exportado**, não uma assinatura digital nem prova de origem. Qualquer pessoa capaz de modificar o arquivo pode recalcular o hash.
- O progresso considera **somente o prefixo sequencial de etapas documentadas**; registros posteriores a um bloqueio não contam. Se uma etapa anterior é reaberta/bloqueada, etapas seguintes ficam bloqueadas mas preservam suas referências, com evento de histórico.
- A etapa 6 exige motivo real de interrupção/falha (incluindo interrupção controlada para teste); a etapa 7 exige **segundo host físico e nova lease/generation distinta**. Não é permitido dispensar failover no aceite desta solução.
- A etapa de admissão exige declaração de custo `COST_ZERO_CONFIRMED` com referência. `COST_UNKNOWN_BLOCKED` e valores sem origem bloqueiam avanço; isso **não certifica** o preço de qualquer host/serviço.
- O encerramento requer referências por tipo (positivo, negativo, replay, efeito externo, artefato, hash, autorização), e todos os campos críticos. **Mesmo 12/12 documentado não significa execução homologada**.
- A importação verifica SHA-256 e todos os IDs/eventos e conflitos **antes** de trocar o estado local; eventos repetidos em um mesmo lote são recusados. O JSON não representa CAS do Builder.
- O progresso representa documentação e **não** progresso real da entrega, homologação física ou SLA.
- Importação limita tamanho (2 MB), quantidade de registros e eventos; dados importados nunca são executados ou injetados como HTML.
- O valor `0` em ações remotas significa que o painel não acionou nenhuma; custo operacional do host e serviços externos não é calculado ou presumido.
- Exportação baixada pelo navegador não comprova checkpoint CAS, armazenamento externo imutável ou retomada nativa. Para isso, ler e testar no plano de controle canônico.

## Fontes consultadas em 19/11/2026
- [Regras globais](https://github.com/ericson-j-santos/chatgpt-operational-rules): main `58dcd4200f412a866278027ba9e433439a03f3b3`
- [ReqSys](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real): main `a05e64bbc58a15314b42cfa9314f1d415535b05b`, issue [#3126](https://github.com/ericson-j-santos/reqsys-v2-enterprise-real/issues/3126), aberta na consulta.
- [Noteri](https://github.com/ericson-j-santos/noteri-runtime): main `64da8ddd06657904cd66d2bf49e6a44f752b7bdf`, issue [#42](https://github.com/ericson-j-santos/noteri-runtime/issues/42), aberta na consulta.
- [Central ReqSys já publicada](https://reqsys-manual-operacional-interativo-g6mwin.v2.appdeploy.ai/).

## Testes de pré-entrega
- `python test_site.py`: interface, cadastro, sequência estrita, custo desconhecido, SHA divergente, lease repetida, campos ausentes, rollback de progresso, duplicidade por chave, histórico duplicado, importação atômica, LGPD, integridade do JSON e responsividade. Não realiza chamadas externas.
- `python test_sources.py`: interface de consulta e contratos GET simulados no Chromium com Playwright; fontes permitidas, seis leituras iniciais, run com jobs e artefatos, comparação de SHA, ausência de escrita, rejeição de origem indevida e erro 403/rate limit.
- `node --check` no JavaScript extraído do HTML.
- As leituras reais de GitHub foram efetuadas na integração conectada durante a elaboração; **a chamada da página no navegador do usuário não foi testada em rede aberta**. Falha de CORS/bloqueio de rede deve resultar em mensagem explícita.

## Publicação do código e rastreabilidade
Código-fonte proposto para `tools/codex-local-online/central-execucoes/` no repositório existente `ericson-j-santos/reqsys-v2-enterprise-real`. Sem substituir `tools/codex-local-online/index.html`, sem PR ou deploy automático. Os testes de navegador locais são validação independente limitada ao protótipo; não são `READY_FOR_PR` do ReqSys.

## Critério de conclusão
O módulo local está implementado e testado; a **leitura via navegador permanece condicionada a rede/CORS**, e a operação real E2E física continua **não homologada**. Este módulo é fornecido como código-fonte para revisão em branch isolada no repositório ReqSys; a publicação de arquivos no GitHub não representa merge, deploy, ativação do runtime ou homologação operacional. Para certificação completa, é necessário acesso autorizado ao runtime ReqSys DEV e ao plano de controle físico, com leitura independente de lease/modelo/checkpoint/efeito. Sem essas evidências, status **PARCIAL**.

## Alteração 1.2 — reparo da interface de governança
- **Antes:** texto livre de etapa podia inflar o progresso sem passar pré-condições; chave idempotente repetida com correlação diferente podia criar segunda ficha; histórico com `event_id` repetido poderia ser incorporado no mesmo lote.
- **Depois:** guardas sequenciais, custeio fail-closed, duas leases distintas, avaliação da cadeia antes de encerramento, cálculo de progresso consecutivo, importação candidata atômica e controles positivos/negativos.
- **Limitação demonstrada:** estes testes provam a interface local. Não existe `READY_FOR_PR` produzido por Builder Ollama, CAS físico, Validator independente no host nem E2E ReqSys DEV resultante desta alteração. A publicação em branch não é homologação ou deploy.
- **Rollback:** restaurar o commit anterior da branch, mediante mudança governada; preservar checkpoint exportado antes de substituir a interface.
