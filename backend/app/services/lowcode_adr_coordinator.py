from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

COORDINATOR_VERSION = '0.1.0'

ADR_AGENT_CATALOG: list[dict[str, Any]] = [
    {'adr': 'ADR-0001', 'dominio': 'arquitetura', 'agente': 'Arquiteto Enterprise', 'motivo': 'Arquitetura Padrão Ouro, contratos, modularização e impacto transversal.'},
    {'adr': 'ADR-0002', 'dominio': 'seguranca', 'agente': 'Agente de Segurança e Governança', 'motivo': 'JWT, CORS, PII/LGPD, secrets, permissões e gates produtivos.'},
    {'adr': 'ADR-0003', 'dominio': 'ambientes', 'agente': 'Agente DevOps de Ambientes', 'motivo': 'Separação dev/hml/prod, variáveis, drift e promoção.'},
    {'adr': 'ADR-0004', 'dominio': 'ci_cd', 'agente': 'Agente DevOps/CI', 'motivo': 'Workflows, testes, quality gates, PR, mergeabilidade e CI verde.'},
    {'adr': 'ADR-0005', 'dominio': 'observabilidade', 'agente': 'Agente de Observabilidade', 'motivo': 'Logs estruturados, auditoria, métricas, rastreabilidade e correlation_id.'},
    {'adr': 'ADR-0006', 'dominio': 'analytics', 'agente': 'Agente de Analytics e BI', 'motivo': 'Indicadores, drill-down, schema-driven UI e scorecards.'},
    {'adr': 'ADR-020', 'dominio': 'integracoes', 'agente': 'Agente de Integrações Corporativas', 'motivo': 'Conectores, permissões sob demanda, APIs externas e Power Platform.'},
    {'adr': 'ADR-021', 'dominio': 'ux_integrada', 'agente': 'Agente Frontend/UX', 'motivo': 'Experiência visual, retorno em tela, protótipos e responsividade.'},
    {'adr': 'ADR-022', 'dominio': 'operacoes_autonomas', 'agente': 'Agente Operacional Autônomo Governado', 'motivo': 'Operação assistida, triagem e remediação controlada.'},
    {'adr': 'ADR-023', 'dominio': 'runtime', 'agente': 'Agente Runtime Health', 'motivo': 'Healthcheck, disponibilidade, remediação, rollback e validação pós-deploy.'},
    {'adr': 'ADR-030', 'dominio': 'governanca_pr', 'agente': 'Agente de Governança de PR', 'motivo': 'Automerge governado, políticas de branch e controle de mudanças.'},
    {'adr': 'ADR-031', 'dominio': 'promocao_runtime', 'agente': 'Agente de Promoção e Risco Runtime', 'motivo': 'Promoção, risco runtime, go/no-go e rollback.'},
    {'adr': 'ADR-032', 'dominio': 'dashboard_operacional', 'agente': 'Agente de Dashboard Operacional', 'motivo': 'Painéis de saúde, semáforo, cards executivos e evidência navegável.'},
    {'adr': 'ADR-035', 'dominio': 'arquitetura_viva', 'agente': 'Agente de Arquitetura Viva', 'motivo': 'Mapas, diagramas vivos, documentação versionada e rastreabilidade.'},
    {'adr': 'ADR-036', 'dominio': 'runtime_publico', 'agente': 'Agente de Runtime Público', 'motivo': 'Fly.io, DuckDNS, boot resiliente e readiness público.'},
    {'adr': 'ADR-037', 'dominio': 'telemetria_enterprise', 'agente': 'Agente OpenTelemetry/Auditoria', 'motivo': 'Telemetria enterprise, correlação, métricas e logs sem PII.'},
    {'adr': 'ADR-038', 'dominio': 'ux_operacional', 'agente': 'Agente UX Operacional', 'motivo': 'UX operacional, estados, filtros, drill-down e responsividade.'},
    {'adr': 'ADR-039', 'dominio': 'qualidade_governanca', 'agente': 'Agente QA/Governança Técnica', 'motivo': 'Testes, matriz de qualidade, evidências e validação paralelizável.'},
    {'adr': 'ADR-040', 'dominio': 'padrao_ouro', 'agente': 'Agente Coordenador de Maturidade Padrão Ouro', 'motivo': 'Consolidação A-E, maturidade, lacunas, Pareto e próximo incremento.'},
    {'adr': 'ADR-041', 'dominio': 'secrets', 'agente': 'Agente de Secrets e Configuração Segura', 'motivo': 'Cofre local, criptografia, diagnóstico e fallback seguro.'},
    {'adr': 'ADR-USER-FINAL-SHELL', 'dominio': 'usuario_final', 'agente': 'Agente de Produto e Usuário Final', 'motivo': 'Jornada final, usabilidade real e clareza para usuário.'},
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


def listar_adr_base_coordenador() -> dict[str, Any]:
    return {
        'schema_version': COORDINATOR_VERSION,
        'idioma': 'pt-BR',
        'fonte_canonica': 'docs/padrao-ouro/ADR_INDEX.md',
        'politica': {
            'fundacionais_primeiro': ['ADR-0001', 'ADR-0002', 'ADR-0003', 'ADR-0004', 'ADR-0005', 'ADR-0006'],
            'modo_execucao': 'dry_run por padrão; execução externa exige aprovação humana ou pipeline autorizado',
            'rastreabilidade_obrigatoria': ['adr', 'agente', 'motivo', 'correlation_id', 'evidencia_esperada'],
        },
        'agentes': ADR_AGENT_CATALOG,
    }


def _selecionar_adrs(objetivo: str, adr_refs: list[str] | None) -> list[dict[str, Any]]:
    selected_refs = {ref.strip().upper() for ref in (adr_refs or []) if ref.strip()}
    objetivo_normalizado = (objetivo or '').strip().lower()

    for keywords, refs in KEYWORD_RULES:
        if any(keyword in objetivo_normalizado for keyword in keywords):
            selected_refs.update(refs)

    if not selected_refs:
        selected_refs.update({'ADR-0001', 'ADR-0002', 'ADR-0004', 'ADR-0005', 'ADR-039'})

    for ref in ['ADR-0001', 'ADR-0002', 'ADR-0004', 'ADR-0005']:
        selected_refs.add(ref)

    catalog_by_adr = {item['adr'].upper(): item for item in ADR_AGENT_CATALOG}
    return sorted(
        [catalog_by_adr[ref] for ref in selected_refs if ref in catalog_by_adr],
        key=lambda item: (0 if item['adr'] in {'ADR-0001', 'ADR-0002', 'ADR-0004', 'ADR-0005'} else 1, item['adr']),
    )


def planejar_coordenacao_por_adr(
    *,
    objetivo: str,
    adr_refs: list[str] | None = None,
    dry_run: bool = True,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    correlation = correlation_id or str(uuid.uuid4())
    agentes = _selecionar_adrs(objetivo, adr_refs)

    roteamento = []
    for ordem, item in enumerate(agentes, start=1):
        roteamento.append(
            {
                'ordem': ordem,
                'agente': item['agente'],
                'adr': item['adr'],
                'dominio': item['dominio'],
                'motivo': item['motivo'],
                'entrada_esperada': {
                    'objetivo': objetivo,
                    'adr_base': item['adr'],
                    'correlation_id': correlation,
                    'idioma': 'pt-BR',
                },
                'saida_esperada': [
                    'decisão recomendada',
                    'riscos e lacunas',
                    'evidência esperada',
                    'próximo incremento seguro',
                ],
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
            'responsabilidade': 'Orquestrar agentes especializados conforme ADR aplicável, com rastreabilidade, evidência e aprovação humana para ações externas.',
            'fonte_decisoria': 'docs/padrao-ouro/ADR_INDEX.md',
        },
        'roteamento': roteamento,
        'guardrails': [
            'Não executar escrita externa sem aprovação humana ou pipeline ALM autorizado.',
            'Preservar correlation_id em chamadas, logs e evidências.',
            'Não expor PII, secrets, tokens ou chaves em prompts, logs ou payloads.',
            'Executar ADRs fundacionais antes de decisões específicas com impacto transversal.',
            'Registrar lacunas, riscos, trade-offs e evidência esperada por agente acionado.',
        ],
        'criterios_de_aceite': [
            'Todo agente chamado possui ADR base, motivo, entrada, saída e evidência esperada.',
            'O plano está em português do Brasil e segue governança Padrão Ouro.',
            'A execução externa permanece bloqueada por dry_run ou despacho governado.',
            'O resultado é consumível via API pelo Hub Low-Code.',
        ],
    }
