from __future__ import annotations

import hashlib
import json
from typing import Final

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.orchestrator import AgileProjectPackage

SUPPORTED_INTEGRATION_TARGETS: Final[tuple[str, ...]] = (
    'jira',
    'azure_devops',
    'github_projects',
    'gitlab',
)


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _content_hash(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode('utf-8')).hexdigest()


def _status_from_package(package: dict) -> str:
    gaps = package.get('governance', {}).get('gaps', [])
    return 'refinement_required' if gaps else 'generated'


def persist_package(db: Session, package: dict) -> dict:
    package_id = str(package['package_id'])
    payload_json = _canonical_json(package)
    content_hash = _content_hash(payload_json)
    targets_json = _canonical_json({'targets': list(SUPPORTED_INTEGRATION_TARGETS)})

    record = (
        db.query(AgileProjectPackage)
        .filter(AgileProjectPackage.package_id == package_id)
        .one_or_none()
    )
    created = record is None

    if record is None:
        record = AgileProjectPackage(
            package_id=package_id,
            correlation_id=package.get('correlation_id'),
            schema_version=str(package.get('schema_version', '1.0.0')),
            status=_status_from_package(package),
            content_hash=content_hash,
            payload_json=payload_json,
            integration_targets_json=targets_json,
            external_references_json='{}',
        )
        db.add(record)
    elif record.content_hash != content_hash:
        record.correlation_id = package.get('correlation_id')
        record.schema_version = str(package.get('schema_version', '1.0.0'))
        record.status = _status_from_package(package)
        record.content_hash = content_hash
        record.payload_json = payload_json
        record.integration_targets_json = targets_json

    db.commit()
    db.refresh(record)
    return serialize_record(record, created=created)


def get_package(db: Session, package_id: str) -> dict | None:
    record = (
        db.query(AgileProjectPackage)
        .filter(AgileProjectPackage.package_id == package_id)
        .one_or_none()
    )
    return serialize_record(record) if record else None


def list_packages(
    db: Session,
    correlation_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    query = db.query(AgileProjectPackage)
    if correlation_id:
        query = query.filter(AgileProjectPackage.correlation_id == correlation_id)
    if status:
        query = query.filter(AgileProjectPackage.status == status)
    records = query.order_by(desc(AgileProjectPackage.created_at)).limit(limit).all()
    return [serialize_record(record) for record in records]


def serialize_record(record: AgileProjectPackage, created: bool | None = None) -> dict:
    result = {
        'package_id': record.package_id,
        'correlation_id': record.correlation_id,
        'schema_version': record.schema_version,
        'status': record.status,
        'content_hash': record.content_hash,
        'package': json.loads(record.payload_json),
        'integration_targets': json.loads(record.integration_targets_json)['targets'],
        'external_references': json.loads(record.external_references_json),
        'created_at': record.created_at.isoformat() if record.created_at else None,
        'updated_at': record.updated_at.isoformat() if record.updated_at else None,
    }
    if created is not None:
        result['created'] = created
    return result
