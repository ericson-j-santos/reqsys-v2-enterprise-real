from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

COORDINATOR_VERSION = '0.1.0'

ADR_AGENT_CATALOG: list[dict[str, Any]] = [
    {
        'adr': 'ADR-0001',
        'titulo': 'Arquitetura Padrão Ouro',
        'dominio': 'arquitetura',
        'agente': 'Arquiteto Enterprise',
        'quando_chamar': 'Decisões transversais, modularização, hexagonalidade, contratos e desacoplamento.',
        'entregaveis': ['decisão arquitetural', 'mapa de impacto', 'contratos preservados'],
    },
    {
        'adr': 'ADR-0002',
        'titulo': 'Segurança e Gates de Produção',
        'dominio': 'seguranca',
        'agente': 'Agente de Segurança e Governança',
        'quando_chamar': 'JWT, CORS, PII/LGPD, secrets, permissões, gates produtivos e revisão de risco.',
        'entregaveis': ['matriz de risco', 'guardrails de segurança', 'bloqueios produtivos'],
    },
    {
        'adr': 'ADR-0003',
        'titulo': 'Ambientes dev/hml/prod',
        'dominio': 'ambientes',
        'agente': 'Agente DevOps de Ambientes',
        'quando_chamar': 'Separação de ambiente, promoção, drift, variáveis e configuração por estágio.',
        'entregaveis': ['matriz de ambientes', 'plano de promoção', 'evidência de drift'],
    },
    {
        'adr': 'ADR-0004',
        'titulo': 'CI/CD e Qualidade',
        'dominio': 'ci_cd',
        'agente': 'Agente DevOps/CI',
        'quando_chamar': 'Workflows, testes, quality gates, PR, mergeabilidade e evidência de CI verde.',
        'entregaveis': ['plano de validação', 'gates obrigatórios', 'evidência de CI'],
    },
    {
        'adr': 'ADR-0005',
        'titulo': 'Observabilidade e Auditoria',
        'dominio': 'observabilidade',
        'agente': 'Agente de Observabilidade',
        'quando_chamar': 'Logs estruturados, correlation_id, auditoria, métricas, rastreabilidade e evidências.',
        'entregaveis': ['plano de telemetria', 'eventos auditáveis', 'correlation_id obrigatório'],
    },
    {
        'adr': 'ADR-0006',
        'titulo': 'Analytics Drill-down Schema-driven',
        'dominio': 'analytics',
        'agente': 'Agente de Analytics e BI',
        'quando_chamar': 'Indicadores, drill-down, schema-driven UI, scorecards e análise operacional.',
        'entregaveis': ['modelo analítico', 'indicadores', 'drill-down executivo'],
    },
    {
        'adr': 'ADR-020',
        'titulo': 'Connection Broker Permission on Demand',
        'dominio': 'integracoes',
        'agente': 'Agente de Integrações Corporativas',
        'quando_chamar': 'Conectores, permissões sob demanda, APIs externas e integração com Power Platform.',
        'entregaveis': ['contrato de integração', 'permissões mínimas', 'plano de fallback'],
    },
    {
        'adr': 'ADR-021',
        'titulo': 'Figma-GitHub Retorno em Tela',
        'dominio': 'ux_integrada',
        'agente': 'Agente Frontend/UX',
        'quando_chamar': 'Experiência visual, retorno em tela, protótipos, responsividade e navegação.',
        'entregaveis': ['fluxo de tela', 'critérios UX', 'evidência visual'],
    },
    {
        'adr': 'ADR-022',
        'titulo': 'Autonomous Operations Platform P0.1',
        'dominio': 'operacoes_autonomas',
        'agente': 'Agente Operacional Autônomo Governado',
        'quando_chamar': 'Operação autônoma assistida, triagem, remediação controlada e execução governada.',
        'entregaveis': ['plano de execução assistida', 'pontos de autorização humana', 'log operacional'],
    },
    {
        'adr': 'ADR-023',
        'titulo': 'Runtime Health Validator + Remediation',
        'dominio': 'runtime',
        'agente': 'Agente Runtime Health',
        'quando_chamar': 'Healthcheck, remediação, disponibilidade, degradação, rollback e validação pós-deploy.',
        'entregaveis': ['health matrix', 'plano de remediação', 'evidência pós-deploy'],
    },
    {
        'adr': 'ADR-030',
        'titulo': 'Governed Dev Automerge',
        'dominio': 'governanca_pr',
        'agente': 'Agente de Governança de PR',
        'quando_chamar': 'Automerge governado, políticas de branch, revisão e controle de mudanças.',
        'entregaveis': ['política de merge', 'gates de PR', 'registro de decisão'],
    },
    {
        'adr': 'ADR-031',
        'titulo': 'Runtime Risk and Promotion Pipeline',
        'dominio': 'promocao_runtime',
        'agente': 'Agente de Promoção e Risco Runtime',
        'quando_chamar': 'Promoção entre ambientes, risco runtime, go/no-go e evidência de estabilização.',
        'entregaveis': ['risk score', 'go/no-go', 'plano de rollback'],
    },
    {
        'adr': 'ADR-032',
        'titulo': 'Operational Health Dashboard Governance',
        'dominio': 'dashboard_operacional',
        'agente': 'Agente de Dashboard Operacional',
        'quando_chamar': 'Painéis de saúde, semáforo, cards executivos, drill-down e evidência navegável.',
        'entregaveis': ['dashboard contract', 'semáforo executivo', 'fontes de evidência'],
    },
    {
        'adr': 'ADR-035',
        'titulo': 'Trilha E — Arquitetura Viva',
        'dominio': 'arquitetura_viva',
        'agente': 'Agente de Arquitetura Viva',
        'quando_chamar': 'Mapas, diagramas vivos, rastreabilidade e documentação versionada.',
        'entregaveis': ['mapa de arquitetura', 'índice vivo', 'rastreabilidade ADR'],
    },
    {
        'adr': 'ADR-036',
        'titulo': 'Trilha A — Runtime Público',
        'dominio': 'runtime_publico',
        'agente': 'Agente de Runtime Público',
        'quando_chamar': 'Fly.io, DuckDNS, boot resiliente, healthcheck público e readiness operacional.',
        'entregaveis': ['smoke público', 'readiness report', 'status de endpoints'],
    },
    {
        'adr': 'ADR-037',
        'titulo': 'Trilha B — Observabilidade Enterprise',
        'dominio': 'telemetria_enterprise',
        'agente': 'Agente OpenTelemetry/Auditoria',
        'quando_chamar': 'Telemetria enterprise, correlação, métricas, logs e auditoria sem PII.',
        'entregaveis': ['plano OTel', 'métricas', 'correlação ponta a ponta'],
    },
    {
        'adr': 'ADR-038',
        'titulo': 'Trilha C — UX Operacional',
        'dominio': 'ux_operacional',
        'agente': 'Agente UX Operacional',
        'quando_chamar': 'UX de operação, semáforo, leitura executiva, filtros, drill-down e responsividade.',
        'entregaveis': ['fluxo UX', 'estado vazio/erro/carregamento', 'critérios responsivos'],
    },
    {
        'adr': 'ADR-039',
        'titulo': 'Trilha D — Qualidade e Governança',
        'dominio': 'qualidade_governanca',
        'agente': 'Agente QA/Governança Técnica',
        'quando_chamar': 'Testes, governança, matriz de qualidade, evidências e validação paralelizável.',
        'entregaveis': ['matriz de testes', 'quality gates', 'evidências de validação'],
    },
    {
        'adr': 'ADR-040',
        'titulo': 'Trilhas Padrão Ouro Consolidadas',
        'dominio': 'padrao_ouro',
        'agente': 'Agente Coordenador de Maturidade Padrão Ouro',
        'quando_chamar': 'Consolidação A-E, maturidade, lacunas, Pareto e próximo incremento seguro.',
        'entregaveis': ['score de maturidade', 'gaps priorizados', 'próximo incremento'],
    },
    {
        'adr': 'ADR-041',
        'titulo': 'Cofre de Segredos Locais',
        'dominio': 'secrets',
        'agente': 'Agente de Secrets e Configuração Segura',
        'quando_chamar': 'Segredos locais, keyring, criptografia, diagnóstico e fallback seguro.',
        'entregaveis': ['matriz de secrets', 'guardrails de cofre', 'diagnóstico seguro'],
    },
    {
        'adr': 'ADR-USER-FINAL-SHELL',
        'titulo': 'User Final Shell',
        'dominio': 'usuario_final',
        'agente': 'Agente de Produto e Usuário Final',
        'quando_chamar': 'Shell visual, jornadas, usabilidade real, navegação final e clareza para usuário.',
        'entregaveis': ['jornada do usuário', 'critérios de aceite UX', 'lacunas de produto'],
    },
]

KEYWORD_RULES: list[tuple[set[str], set[str]]] = [
    ({'seguranca', 'security', 'jwt', 'cors', 'pii', 'lgpd', 'secret', 'secrets', 'cofre'}, {'ADR-0002', 'ADR-041'}),
    ({'ci', 'cd', 'workflow', 'github', 'pr', 'merge', 'teste', 'testes'}, {'ADR-0004', 'ADR-030', 'ADR-039'}),
    ({'runtime', 'health', 'deploy', 'fly', 'duckdns', 'rollback', 'producao', 'produção'}, {'ADR-023', 'ADR-031', 'ADR-036'}),
    ({'observabilidade', 'log', 'logs', 'auditoria', 'correlation', 'correlation_id', 'telemetria'}, {'ADR-0005', 'ADR-037'}),
    ({'dashboard', 'indicador', 'analytics', 'bi', 'score', 'drill'}, {'ADR-0006', 'ADR-032', 'ADR-038'}),
    ({'api', 'integracao', 'integração', 'power', 'automate', 'dataverse', 'connector', 'conector'}, {'ADR-020'}),
    ({'frontend', 'ux', 'ui', 'tela', 'responsivo', 'usuario', 'usuário'}, {'ADR-021', 'ADR-038', 'ADR-USER-FINAL-SHELL'}),
    ({'arquitetura', 'adr', 'hexagonal', 'modular', 'contrato'}, {'ADR-0001', 'ADR-035'}),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalizar(texto: str) -> str:
    return (texto or '').strip().lower()


def listar_adr_base_coordenador() -> dict[str, Any]:
    return {
        'schema_version': COORDINATOR_VERSION,
        'idioma': 'pt-BR',
        'fonte_canonica': 'docs/padrao-ouro/ADR_INDEX.md',
        'politica': {
            'fundacionais_primeiro': ['ADR-0001', 'ADR-0002', 'ADR-0003', 'ADR-0004', 'ADR-0005', 'ADR-0006'],
            'modo_execucao': 'planejamento governado por padrão; execução externa exige aprovação humana ou pipeline autorizado',
            'rastreabilidade_obrigatoria': ['adr', 'agente', 'motivo', 'evidencia_esperada', 'correlation_id'],
        },
        'agentes': ADR_AGENT_CATALOG,
    }


def _selecionar_adrs(objetivo: str, adr_refs: list[str] | None) -> list[dict[str, Any]]:
    explicit_refs = {ref.strip().upper() for ref in (adr_refs or []) if ref.strip()}
    objetivo_normalizado = _normalizar(objetivo)
    selected_refs = set(explicit_refs)

    for keywords, refs in KEYWORD_RULES:
        if any(keyword in objetivo_normalizado for keyword in keywords):
            selected_refs.update(refs)

    if not selected_refs:
        selected_refs.update({'ADR-0001', 'ADR-0002', 'ADR-0004', 'ADR-0005', 'ADR-039'})

    catalog_by_adr = {item['adr'].upper(): item for item in ADR_AGENT_CATALOG}
    selected = [catalog_by_adr[ref] for ref in selected_refs if ref in catalog_by_adr]

    fundacionais = ['ADR-0001', 'ADR-0002', 'ADR-0004', 'ADR-0005']
    for ref in fundacionais:
        if ref in catalog_by_adr and all(item['adr'] != ref for item in selected):
            selected.append(catalog_by_adr[ref])

    return sorted(selected, key=lambda item: (0 if item['adr'] in fundacionais else 1, item['adr']))


def planejar_coordenacao_por_adr(
    *,
    objetivo: str,
    adr_refs: list[str] | None = None,
    dry_run: bool = True,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    correlation = correlation_id or str(uuid.uuid4())
    agentes = _selecionar_adrs(objetivo, adr_refs)

    chamadas = []
    for ordem, item in enumerate(agentes, start=1):
        chamadas.append(
            {
                'ordem': ordem,
                'agente': item['agente'],
                'adr': item['adr'],
                'dominio': item['dominio'],
                'motivo': item['quando_chamar'],
                'entrada_esperada': {
                    'objetivo': objetivo,
                    'adr_base': item['adr'],
                    'correlation_id': correlation,
                    'idioma': 'pt-BR',
                },
                'saida_esperada': item['entregaveis'],
                'modo': 'dry_run_plan' if dry_run else 'ready_for_governed_dispatch',
            }
        )

    return {
        'schema_version': COORDINATOR_VERSION,
        'capability': 'LowCode ADR Agent Coordinator',
        'idioma': 'pt-BR',
        'status': 'planned' if dry_run else 'ready_for_governed_dispatch',
        'generated_at': _utc_now(),
        'correlation_id': correlation,
        'objetivo': objetivo,
        'coordenador': {
            'nome': 'Coordenador ReqSys ADR',
            'responsabilidade': 'Orquestrar agentes especializados conforme ADR aplicável, mantendo rastreabilidade, evidência e aprovação humana para ações externas.',
            'fonte_decisoria': 'docs/padrao-ouro/ADR_INDEX.md',
        },
        'roteamento': chamadas,
        'guardrails': [
            'Não executar escrita externa sem aprovação humana ou pipeline ALM autorizado.',
            'Sempre preservar correlation_id em chamadas, logs e evidências.',
            'Não expor PII, secrets, tokens ou chaves em prompts, logs ou payloads.',
            'Executar ADRs fundacionais antes de decisões específicas quando houver impacto transversal.',
            'Registrar lacunas, riscos, trade-offs e evidência esperada por agente acionado.',
        ],
        'criterios_de_aceite': [
            'Todo agente chamado possui ADR base, motivo, entrada, saída e evidência esperada.',
            'O plano está em português do Brasil e segue governança Padrão Ouro.',
            'A execução externa permanece bloqueada por dry_run ou despacho governado.',
            'O resultado é consumível via API pelo Hub Low-Code.',
        ],
    }
