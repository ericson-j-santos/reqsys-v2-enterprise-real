"""Provisionamento governado de Power Automate flows.

P0 nao cria flows diretamente pelo runtime do ReqSys. O runtime gera um manifesto
rastreavel e, quando configurado, despacha um GitHub Actions workflow que reutiliza
o repositorio ALM `reqsys-powerplatform-alm` e o padrao LowCodeFactory/pac CLI.

P0.1 adiciona registry runtime persistente para governanca operacional.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.power_automate_provisioning import PowerAutomateProvisioningRegistry

logger = logging.getLogger('reqsys.power_automate_provisioning')

_WORKFLOW_FILE = 'power-automate-flow-provisioning-p0.yml'
_DEFAULT_ALM_REPO = 'ericson-j-santos/reqsys-powerplatform-alm'
_SUPPORTED_TRIGGER_TYPES = {'HttpRequest', 'Recurrence', 'Manual'}
_ALLOWED_STATUSES = {
    'planned',
    'dispatched',
    'running',
    'succeeded',
    'failed',
    'rollback_required',
    'pending_configuration',
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_json(value: Any) -> str:
    try:
        return json.dumps(value or {}, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({'raw': str(value)}, ensure_ascii=False)


def _from_json(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {'raw': value}


def normalizar_trigger_type(trigger_type: str | None) -> str:
    value = (trigger_type or 'HttpRequest').strip()
    if value not in _SUPPORTED_TRIGGER_TYPES:
        raise ValueError(f'TriggerType invalido: {value}. Valores aceitos: {sorted(_SUPPORTED_TRIGGER_TYPES)}')
    return value


def normalizar_status(status: str | None) -> str:
    value = (status or 'planned').strip().lower()
    if value not in _ALLOWED_STATUSES:
        raise ValueError(f'Status invalido: {value}. Valores aceitos: {sorted(_ALLOWED_STATUSES)}')
    return value


def gerar_manifesto_provisionamento_flow(
    display_name: str,
    trigger_type: str = 'HttpRequest',
    description: str = '',
    target_environment: str = 'dev',
    solution_name: str = 'ReqSysAutomacao',
    correlation_id: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Gera contrato de provisionamento sem expor segredo.

    O manifesto e idempotente por `flow_id` e deve ser executado pelo pipeline ALM.
    """

    nome = display_name.strip()
    if len(nome) < 5:
        raise ValueError('display_name deve ter pelo menos 5 caracteres')

    trigger = normalizar_trigger_type(trigger_type)
    flow_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{solution_name}:{target_environment}:{nome}')).upper()
    corr = correlation_id or str(uuid.uuid4())
    alm_repo = settings.github_alm_repo or _DEFAULT_ALM_REPO

    return {
        'schema_version': '1.0.0',
        'capability': 'Power Automate Flow Provisioning P0',
        'status': 'planned' if dry_run else 'dispatch_requested',
        'correlation_id': corr,
        'generated_at': _utc_now(),
        'source': {
            'system': 'ReqSys',
            'component': 'hub-lowcode',
            'runtime_environment': settings.normalized_environment,
        },
        'target': {
            'alm_repository': alm_repo,
            'workflow_file': _WORKFLOW_FILE,
            'environment': target_environment,
            'solution_name': solution_name,
        },
        'flow': {
            'flow_id': flow_id,
            'display_name': nome,
            'trigger_type': trigger,
            'description': description.strip(),
            'connection_strategy': 'http_only_sem_user_connections_no_p0',
        },
        'governance': {
            'mode': 'solution_import_via_pac_cli',
            'reuse_detected': 'reqsys-powerplatform-alm/scripts/LowCodeFactory.psm1',
            'requires_human_or_pipeline_approval': True,
            'secrets_required': [
                'POWERPLATFORM_APP_ID',
                'POWERPLATFORM_CLIENT_SECRET',
                'POWERPLATFORM_TENANT_ID',
                'DEV_ENVIRONMENT_URL ou TARGET_ENVIRONMENT_URL',
            ],
            'non_goals_p0': [
                'nao executar Flow Maker API diretamente pelo backend',
                'nao persistir client_secret no ReqSys',
                'nao criar conexoes de usuario automaticamente',
            ],
        },
    }


def serializar_registry(item: PowerAutomateProvisioningRegistry) -> dict[str, Any]:
    return {
        'id': item.id,
        'correlation_id': item.correlation_id,
        'status': item.status,
        'ambiente': item.ambiente,
        'solution_name': item.solution_name,
        'flow_id': item.flow_id,
        'flow_display_name': item.flow_display_name,
        'trigger_type': item.trigger_type,
        'workflow_run_url': item.workflow_run_url,
        'artifact_url': item.artifact_url,
        'executed_by': item.executed_by,
        'retry_count': item.retry_count,
        'manifesto': _from_json(item.manifesto_json),
        'dispatch': _from_json(item.dispatch_json),
        'erro': item.erro,
        'created_at': item.created_at.isoformat() if item.created_at else None,
        'updated_at': item.updated_at.isoformat() if item.updated_at else None,
    }


def registrar_manifesto_provisionamento(
    db: Session,
    manifesto: dict[str, Any],
    status: str = 'planned',
    dispatch: dict[str, Any] | None = None,
    executed_by: str = 'reqsys',
) -> PowerAutomateProvisioningRegistry:
    resolved_status = normalizar_status(status)
    correlation_id = manifesto['correlation_id']
    existing = db.execute(
        select(PowerAutomateProvisioningRegistry).where(
            PowerAutomateProvisioningRegistry.correlation_id == correlation_id
        )
    ).scalar_one_or_none()

    item = existing or PowerAutomateProvisioningRegistry(correlation_id=correlation_id)
    item.status = resolved_status
    item.ambiente = manifesto['target']['environment']
    item.solution_name = manifesto['target']['solution_name']
    item.flow_id = manifesto['flow']['flow_id']
    item.flow_display_name = manifesto['flow']['display_name']
    item.trigger_type = manifesto['flow']['trigger_type']
    item.executed_by = executed_by
    item.manifesto_json = _to_json(manifesto)
    item.dispatch_json = _to_json(dispatch or {})
    item.erro = str((dispatch or {}).get('error') or (dispatch or {}).get('reason') or '')[:2000]
    if dispatch and dispatch.get('workflow_run_url'):
        item.workflow_run_url = dispatch['workflow_run_url']
    if not existing:
        db.add(item)
    db.commit()
    db.refresh(item)
    return item


def atualizar_status_provisionamento(
    db: Session,
    correlation_id: str,
    status: str,
    workflow_run_url: str | None = None,
    artifact_url: str | None = None,
    erro: str | None = None,
) -> PowerAutomateProvisioningRegistry:
    item = db.execute(
        select(PowerAutomateProvisioningRegistry).where(
            PowerAutomateProvisioningRegistry.correlation_id == correlation_id
        )
    ).scalar_one_or_none()
    if item is None:
        raise ValueError(f'Provisionamento nao encontrado: {correlation_id}')

    item.status = normalizar_status(status)
    if workflow_run_url is not None:
        item.workflow_run_url = workflow_run_url
    if artifact_url is not None:
        item.artifact_url = artifact_url
    if erro is not None:
        item.erro = erro[:2000]
    db.commit()
    db.refresh(item)
    return item


def listar_registry_provisionamentos(
    db: Session,
    ambiente: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(PowerAutomateProvisioningRegistry).order_by(PowerAutomateProvisioningRegistry.created_at.desc()).limit(limit)
    if ambiente:
        stmt = stmt.where(PowerAutomateProvisioningRegistry.ambiente == ambiente)
    if status:
        stmt = stmt.where(PowerAutomateProvisioningRegistry.status == normalizar_status(status))
    return [serializar_registry(item) for item in db.execute(stmt).scalars().all()]


def resumo_registry_provisionamentos(db: Session) -> dict[str, Any]:
    itens = listar_registry_provisionamentos(db, limit=500)
    total = len(itens)
    por_status: dict[str, int] = {}
    por_ambiente: dict[str, int] = {}
    for item in itens:
        por_status[item['status']] = por_status.get(item['status'], 0) + 1
        por_ambiente[item['ambiente']] = por_ambiente.get(item['ambiente'], 0) + 1

    sucesso = por_status.get('succeeded', 0)
    falha = por_status.get('failed', 0) + por_status.get('rollback_required', 0)
    taxa_sucesso = round((sucesso / total) * 100, 2) if total else 0.0
    risco = 'baixo' if falha == 0 else 'medio' if falha <= 2 else 'alto'

    ambientes = []
    for ambiente in sorted(por_ambiente.keys()):
        subset = [item for item in itens if item['ambiente'] == ambiente]
        ultimo = subset[0] if subset else None
        ambientes.append({
            'ambiente': ambiente,
            'total': len(subset),
            'ultimo_status': ultimo['status'] if ultimo else 'sem_dados',
            'ultimo_correlation_id': ultimo['correlation_id'] if ultimo else None,
            'semaforo': 'verde' if ultimo and ultimo['status'] in {'succeeded', 'dispatched', 'planned'} else 'amarelo',
        })

    return {
        'schema_version': '1.0.0',
        'capability': 'Power Automate Flow Provisioning Registry P0.1',
        'generated_at': _utc_now(),
        'total': total,
        'por_status': por_status,
        'por_ambiente': por_ambiente,
        'taxa_sucesso_percentual': taxa_sucesso,
        'risco_operacional': risco,
        'ambientes': ambientes,
    }


async def despachar_workflow_provisionamento(manifesto: dict[str, Any]) -> dict[str, Any]:
    """Despacha GitHub Actions workflow quando GITHUB_PAT estiver configurado.

    Retorna degradado quando o token nao existe; isso permite ambiente DEV seguro.
    """

    repo = manifesto['target']['alm_repository']
    token = settings.github_pat
    if not token:
        return {
            'dispatched': False,
            'configured': False,
            'reason': 'GITHUB_PAT nao configurado no ReqSys',
            'workflow_file': _WORKFLOW_FILE,
            'repository': repo,
            'correlation_id': manifesto['correlation_id'],
        }

    url = f'https://api.github.com/repos/{repo}/actions/workflows/{_WORKFLOW_FILE}/dispatches'
    payload = {
        'ref': 'main',
        'inputs': {
            'display_name': manifesto['flow']['display_name'],
            'trigger_type': manifesto['flow']['trigger_type'],
            'target_environment': manifesto['target']['environment'],
            'solution_name': manifesto['target']['solution_name'],
            'correlation_id': manifesto['correlation_id'],
            'dry_run': 'false',
        },
    }
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28',
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload, headers=headers)
        if response.status_code == 204:
            return {
                'dispatched': True,
                'configured': True,
                'repository': repo,
                'workflow_file': _WORKFLOW_FILE,
                'workflow_run_url': f'https://github.com/{repo}/actions/workflows/{_WORKFLOW_FILE}',
                'correlation_id': manifesto['correlation_id'],
            }
        logger.warning('provisionamento_flow_dispatch_http_%s body=%s', response.status_code, response.text[:300])
        return {
            'dispatched': False,
            'configured': True,
            'repository': repo,
            'workflow_file': _WORKFLOW_FILE,
            'status_code': response.status_code,
            'error': response.text[:500],
            'correlation_id': manifesto['correlation_id'],
        }
    except Exception as exc:
        logger.warning('provisionamento_flow_dispatch_erro=%s', exc)
        return {
            'dispatched': False,
            'configured': True,
            'repository': repo,
            'workflow_file': _WORKFLOW_FILE,
            'error': str(exc),
            'correlation_id': manifesto['correlation_id'],
        }
