# Teams Gateway Control Center — recuperação de código

## Objetivo

Preservar no GitHub o código recuperável do projeto **Teams Gateway Control Center** sem alterar o frontend/runtime canônico do ReqSys.

## Fonte

- Projeto de origem: `sites-project://appgprj_6a615cfc7c9881918dee3af3303d631a`
- Artefato recuperado e preservado neste diretório: `index.html`
- Fonte do artefato: biblioteca ChatGPT, arquivo `teams_gateway_control_center_autocontido_v2.html`, criado em 2026-09-03.
- Estado: **recuperação parcial e autocontida**. O snapshot completo do projeto Sites não está acessível pela conexão atual.

## O que este diretório contém

O `index.html` preserva uma versão funcional offline com:

- layout e interações do Control Center;
- inventário dos endpoints Teams Gateway/Hub Low-Code;
- filtros e detalhamento de histórico;
- consulta opcional a `/v1/teams-gateway/status`;
- exportação dos dados demonstrativos em JSON;
- trecho recuperado do cliente `teamsGateway.js`.

Os dados operacionais embutidos são explicitamente demonstrativos e os endereços de exemplo usam domínio `.invalid`.

## Relação com o código canônico

A implementação operacional continua no ReqSys. Este diretório é apenas uma recuperação/versionamento do artefato visual produzido fora do repositório e **não substitui** o frontend Vue/Vite nem os serviços Teams Gateway existentes.

Referências internas úteis:

- `frontend/src/views/PainelIntegracaoView.vue`
- `docs/servicos/teams-notification-control-center.md`
- `backend/app/api/teams_gateway.py`
- `backend/app/services/teams_gateway.py`

## Limitação conhecida

O pacote-fonte original completo do projeto Sites, historicamente composto por uma aplicação Next.js/React com múltiplos arquivos, não pôde ser materializado nesta sessão. Por isso esta recuperação não declara equivalência com aquele snapshot.

Quando o snapshot completo voltar a ficar acessível, ele deve ser incorporado em incremento separado, preservando proveniência e sem sobrescrever silenciosamente esta recuperação.

## Segurança

- Nenhum segredo ou credencial foi intencionalmente incorporado.
- Nenhum deploy ou promoção de ambiente é realizado por este diretório.
- Nenhuma alteração de runtime é necessária para abrir o HTML localmente.
