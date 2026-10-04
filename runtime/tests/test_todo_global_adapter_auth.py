import httpx
import pytest

from app.core.components import build_runtime_components
from app.core.config import RuntimeSettings
from app.infrastructure.http.httpx_gateway import HttpxGateway


@pytest.mark.asyncio
async def test_service_token_e_enviado_somente_ao_adapter_configurado():
    seen: list[tuple[str, str | None, str | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (
                str(request.url),
                request.headers.get('X-Service-Token'),
                request.headers.get('X-Correlation-Id'),
            )
        )
        return httpx.Response(200, json={'ok': True})

    target = 'https://reqsys-api.fly.dev/api/internal/todo-global/upsert'
    gateway = HttpxGateway(
        service_token='service-secret',
        service_token_url=target,
        transport=httpx.MockTransport(handler),
    )

    await gateway.post_json(target, {'value': 1}, 'corr-target-0001')
    await gateway.post_json('https://example.invalid/other', {'value': 2}, 'corr-other-0002')

    assert seen[0][1] == 'service-secret'
    assert seen[0][2] == 'corr-target-0001'
    assert seen[1][1] is None
    assert seen[1][2] == 'corr-other-0002'


def test_runtime_components_configuram_token_somente_para_url_todo_global():
    target = 'https://reqsys-api.fly.dev/api/internal/todo-global/upsert'
    settings = RuntimeSettings(
        todo_global_adapter_url=target,
        todo_global_service_token='service-secret',
    )
    components = build_runtime_components(settings)
    gateway = components.service._http_gateway

    assert gateway._service_token == 'service-secret'
    assert gateway._service_token_url == target
