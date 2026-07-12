"""Rotas da Copilot Studio Multiagent Factory integradas ao Hub Low-Code."""

from fastapi import APIRouter

from app.api import hub_lowcode
from app.core.envelope import ok
from app.schemas.copilot_studio_solution import CopilotStudioSolutionGenerateRequest
from app.services.copilot_studio_factory import gerar_copilot_studio_solution

router = APIRouter(prefix='/copilot-studio', tags=['Hub Low-Code & IA'])


@router.post('/generate')
def copilot_studio_solution_generate(payload: CopilotStudioSolutionGenerateRequest):
    """Gera blueprint completo da solução multiagente sem escrita externa."""
    solution = gerar_copilot_studio_solution(payload)
    return ok(solution, solution['correlation_id'])


@router.post('/generate/canvas')
def copilot_studio_solution_generate_canvas(payload: CopilotStudioSolutionGenerateRequest):
    """Gera a visão de canvas da solução multiagente."""
    solution = gerar_copilot_studio_solution(payload)
    return ok(
        {
            'solution_name': solution['solution_name'],
            'display_name': solution['display_name'],
            'target_environment': solution['target_environment'],
            'canvas_markdown': solution['canvas_markdown'],
            'orchestrator': solution['orchestrator'],
            'agents': solution['agents'],
        },
        solution['correlation_id'],
    )


hub_lowcode.router.include_router(router)
