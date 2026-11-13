# FluxoContratos — front-end do painel de lotes

Exportação do front-end publicado no AppDeploy, com fidelidade de conteúdo e sem inclusão do backend.

- Aplicação de origem: `fluxocontratos-central-governada-903pk6`
- Versão da fonte AppDeploy: `1794533244446`
- Site de homologação: https://fluxocontratos-central-governada-903pk6.v2.appdeploy.ai/
- Regras operacionais vigentes: versão `1.6.21`, SHA `58dcd4200f412a866278027ba9e433439a03f3b3`
- Base do GitHub: `a05e64bbc58a15314b42cfa9314f1d415535b05b`
- Branch de arquivo isolada: `feat/fluxocontratos-frontend-appdeploy-1794533244446`

## O que inclui

- React com TypeScript, Vite, CSS e configurações necessárias ao projeto de interface.
- Tela com fila de lotes, classificação de falhas, relatório local e cadastro de hash de scripts.
- `tests/tests.json` especifica cinco testes, mas a publicação do código no GitHub NÃO comprova sua aprovação.

## Limitações e segurança

- O front-end importa `@appdeploy/client`, fornecido pela plataforma AppDeploy. **Não é um aplicativo standalone** e requer SDK e backend compatíveis para compilar e funcionar fora da plataforma original.
- O servidor de origem, o interno e o sistema corporativo não estão conectados. Não há transferência nem publicação real de PDFs.
- Todos os números no painel são declarações de usuários, não verificação física independente dos 110 mil contratos.
- Nada foi integrado à `main`; não foi feito merge nem deploy de produção por este versionamento.
- Sem segredos, PDFs de clientes, dados pessoais ou configuração de acesso ao servidor nesta exportação.
- Sem Docker, custo adicional autorizado R$ 0,00 e operação fail-closed.

## Arquivos

- `index.html`
- `package.json`
- `postcss.config.js`
- `tailwind.config.js`
- `tsconfig.json`
- `vite.config.ts`
- `src/main.tsx`
- `src/App.tsx`
- `src/index.css`
- `tests/tests.json`

## Validação que ainda falta

A versão publicada pelo AppDeploy foi reportada como `ready` sem erros na inspeção automática da implantação. Isso não atesta testes de autenticação, persistência e fluxo corporativo. Para concluir é necessário executar testes de interface, negativos, segurança, idempotência e E2E real em homologação, vinculados ao SHA atual, com leitura independente.

## Integridade

Cada arquivo foi relido via GitHub e comparado em texto com a versão de origem. A versão canônica desta cópia é o SHA da branch, não um nome de arquivo nem um resumo do e-mail.
