# ReqSys Host Readiness — painel e API DEV

**Estado:** protótipo operacional governado; integração física de fontes independentes **pendente**. Sem Docker, sem dispatch, sem merge e sem acesso remoto. Este pacote pode ser versionado em `tools/host-readiness-dashboard/` do ReqSys, mas não está automaticamente publicado.

## Contrato e fronteira de confiança

A UI mantém registros locais como anotações não autenticadas. A API consulta somente snapshots em SQLite, sem endpoints de mutação. Uma CLI **separada** importa recibos HMAC emitidos por um validador externo independente (não pelo host avaliado), exigindo `SESSION_LAUNCH_OK`, SHA integral, perfil NORMAL, identidade física fixa, onze gates explícitos, custo comprovado e hashes de readback iguais. Rejeita assinatura inválida, tempo antigo (>300 s), horário futuro, conflito de evento e identidade divergente. O armazenamento tem readback SHA-256 próprio, mas isso **não** prova readback do host.

A fonte externa real ainda precisa gerar um recibo autenticado a partir da API oficial GitHub e do Gateway governado; **não existe coletor implementado nem runner instalado por este pacote**. A assinatura só pode ser gerada após verificação efetiva independente dos bytes/condições do host; um HMAC sobre dados inventados é inseguro. Sem recibo atual, todos os hosts permanecem `ready_for_work=false`. Um pickup individual nunca certifica continuidade física: `continuity_certified=false` até implementação e execução do contrato E2E entre hosts.

## Uso local autorizado (DEV, loopback)

Requer Python 3.10+; não necessita pip, Docker, PostgreSQL nem serviços pagos. Os comandos abaixo são exemplos para **sandbox DEV**; execução em host real requer `session_launcher`, `SESSION_LAUNCH_OK` e Command Gateway, conforme regras canônicas.

Defina por meio de gerenciador seguro de configuração as variáveis:

- `REQSYS_READINESS_DB`: caminho **absoluto**, privado e persistente para SQLite;
- `REQSYS_READINESS_VIEWER_TOKEN`: senha aleatória com pelo menos 24 caracteres, **não versionada**;
- `REQSYS_READINESS_RULES_SHA`: SHA integral aprovado das regras;
- `REQSYS_READINESS_ATTEST_KEY`: chave de pelo menos 32 caracteres **compartilhada apenas com o validador independente**, não versionada.

Servidor de consulta local: `python -m api.readiness serve --port 8765`. Visite `http://127.0.0.1:8765/` e informe qualquer usuário e a senha de leitura. Servidor aceita exclusivamente o endereço de loopback e requer Basic Auth. **Não expor esse HTTP diretamente à rede.** Para acesso remoto, exigir gateway autenticado, HTTPS e uma revisão de segurança específica antes de habilitar.

Ingestão manual **somente depois** de receber o JSON assinado e aprovado de um validador governado: `python -m api.readiness ingest /caminho/recibo.json`. Essa ação grava apenas o banco de evidências local, não controla hosts. Não gerar recibos artificialmente fora dos testes. Cada `event_id` é idempotente; replay diferente com mesmo ID é rejeitado.

API: `GET /api/v1/readiness` com autenticação Basic, `Cache-Control: no-store`. Métodos `POST`, `PUT`, `PATCH` e `DELETE` são recusados. Nenhuma autorização, segredo ou operação de controle remoto é transmitido ao navegador pelo código-fonte.

## Testes e gates

`python -m unittest discover -s tests -v` cobre assinatura adulterada, identidade/SHA divergentes, expiração, futuro, falha de gate, replay idempotente, conflito, autenticação HTTP real, método proibido, disponibilidade vazia e isolamento de continuidade. `node --check` valida sintaxe JS extraída do HTML. E2E em dois hosts físicos e readback de fonte independente **não executados**; revisão/CI da branch pendentes.

## Segurança e responsabilidades

Owner do produto: ReqSys. Validador e contrato E2E: E2E Platform. Coletor de evidências: Runtime Platform. Fonte de verdade para TODO: TODO Global (sem sincronização automática neste pacote). Regras: `chatgpt-operational-rules` 1.6.20, `main@86abe65b22781c2f608a7d7286ce3a28cd48aaaf`.
## Observação auxiliar de pickups GitHub (sem atestado operacional)

Uma consulta opcional `GET /api/v1/github-observations`, protegida pelo mesmo HTTP Basic local, obtém somente dados de jobs dos repositórios permitidos via API oficial do GitHub. A versão de observação preserva `ready_for_work=false` e `continuity_certified=false` **mesmo com job concluído**: não autentica recibo do Gateway, perfil, lease, dependências e custo. Não altera banco SQLite, não despacha trabalho nem executa comandos nos hosts.

A variável de ambiente opcional `REQSYS_GITHUB_READ_TOKEN` permite acessar a API oficial respeitando limites de taxa; o valor nunca é devolvido na resposta. Não configurar URL livre, usar serviço externo, expor HTTP além do loopback ou utilizar este endpoint como certificado. A ausência de observações é bloqueio, não indicação de computador desligado. Validação DEV: `python -m unittest discover -s tests -v`, incluindo testes de rede simulada e autenticação HTTP. Ativação em host ainda exige sessão governada, Gateway, configuração protegida e evidência física contemporânea.
