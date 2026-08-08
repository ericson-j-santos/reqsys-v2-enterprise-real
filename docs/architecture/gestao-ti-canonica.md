# Camada Canônica de Gestão de TI

## Decisão

O ReqSys permanece como plataforma-mãe. A camada canônica adiciona uma identidade estável para serviços de TI sem substituir ou renomear `requisito_id`.

`servico_id` é UUID imutável armazenado como texto de 36 caracteres para portabilidade entre SQLite, PostgreSQL e SQL Server. O código do serviço é identificador humano e pode ser governado separadamente.

## Contratos

- Catálogo: `GET /api/requisitos/gestao-ti/servicos`
- Cadastro administrativo: `POST /api/requisitos/gestao-ti/servicos`
- Vínculo administrativo: `POST /api/requisitos/gestao-ti/vinculos`
- Painel operacional: `GET /api/requisitos/gestao-ti/painel`
- Leitura para Power BI: `GET /api/requisitos/gestao-ti/consulta/requisitos-servicos`

As mutações exigem JWT com papel `admin`. As consultas são somente leitura e não escrevem no núcleo de requisitos.

## Compatibilidade e cardinalidade

O vínculo fica em tabela própria e possui unicidade em `requisito_id`. Assim, um requisito pertence a no máximo um serviço e um serviço pode agregar muitos requisitos. Registros existentes continuam válidos e aparecem no painel como “sem serviço” até o mapeamento.

## Observabilidade e mensageria

- Todas as mutações registram auditoria e `correlation_id`.
- O painel incorpora o estado real da fila operacional já existente.
- Teams deve consumir eventos via outbox/auditoria; este incremento não adiciona chamada direta ao Graph.
- Erros definitivos são derivados da DLQ existente.
- O contrato do Power BI é somente leitura.

## Implantação

1. Executar os testes do backend.
2. Aplicar `backend/migrations/20260808_gestao_ti_canonica.sql` em desenvolvimento.
3. Cadastrar o serviço `REQSYS`.
4. Mapear requisitos por lote governado.
5. Validar painel, auditoria, logs e contrato Power BI.
6. Promover por DEV → HOM → PROD.

## Indicadores iniciais

- serviços ativos;
- requisitos totais;
- requisitos vinculados;
- requisitos sem serviço;
- cobertura de vínculo;
- fila aguardando/processando;
- DLQ;
- idade da mensagem mais antiga.

## Reversibilidade

A alteração é aditiva. A reversão da aplicação remove apenas o registro das novas rotas e modelos. A reversão física das tabelas deve ocorrer somente depois de confirmar que nenhum consumidor usa os contratos.
