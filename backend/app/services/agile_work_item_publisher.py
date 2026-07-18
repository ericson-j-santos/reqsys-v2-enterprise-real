from __future__ import annotations

import hashlib
from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

SUPPORTED_AGILE_PUBLISHERS = (
    'jira',
    'azure_devops',
    'github_projects',
    'gitlab',
)


@dataclass(frozen=True)
class AgilePublishRequest:
    package_id: str
    provider: str
    correlation_id: str | None = None
    dry_run: bool = True


class AgileWorkItemPublisher(Protocol):
    provider: str

    @abstractmethod
    def publish(self, package: dict, request: AgilePublishRequest) -> dict:
        """Publica um pacote Agile no provider configurado."""
        raise NotImplementedError


def build_idempotency_key(package_id: str, provider: str) -> str:
    raw = f'{provider}:{package_id}'.encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


class DryRunAgilePublisher:
    def __init__(self, provider: str):
        if provider not in SUPPORTED_AGILE_PUBLISHERS:
            raise ValueError(f'unsupported_agile_publisher:{provider}')
        self.provider = provider

    def publish(self, package: dict, request: AgilePublishRequest) -> dict:
        if request.provider != self.provider:
            raise ValueError('publisher_provider_mismatch')

        project = package.get('project', {})
        scrum = package.get('scrum', {})
        return {
            'schema_version': '1.0.0',
            'provider': self.provider,
            'mode': 'dry_run',
            'package_id': request.package_id,
            'correlation_id': request.correlation_id,
            'idempotency_key': build_idempotency_key(request.package_id, self.provider),
            'work_item': {
                'title': project.get('title'),
                'description': scrum.get('user_story'),
                'epic': scrum.get('epic'),
                'acceptance_criteria': scrum.get('acceptance_criteria', []),
                'story_points': scrum.get('story_points_suggested'),
                'priority': project.get('priority'),
                'labels': ['reqsys', 'agile', self.provider],
            },
            'external_reference': None,
            'executed': False,
        }


def get_agile_publisher(provider: str) -> AgileWorkItemPublisher:
    return DryRunAgilePublisher(provider)
