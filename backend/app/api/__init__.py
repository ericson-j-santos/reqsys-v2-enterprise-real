"""Bootstrap do pacote de APIs."""

import app.api.copilot_studio  # noqa: F401
import app.api.requisitos_runtime_inspection  # noqa: F401
import app.api.requisitos_runtime_transition  # noqa: F401

# O router de governanca e anexado ao router existente de diagramas para
# preservar o ponto unico de inclusao utilizado pelo app.main.
from app.api import diagram_version_governance, diagramas  # noqa: E402

# O coordenador ADR/PDR e anexado ao Hub Low-Code para preservar o prefixo
# /v1/hub-lowcode e evitar novo ponto de inclusao no app.main.
from app.api import hub_lowcode, prompt_development_coordinator  # noqa: E402

diagramas.router.include_router(diagram_version_governance.router)
hub_lowcode.router.include_router(prompt_development_coordinator.router)
