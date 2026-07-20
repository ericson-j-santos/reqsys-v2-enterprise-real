"""Bootstrap do pacote de APIs."""

import app.api.copilot_studio  # noqa: F401
import app.api.requisitos_runtime_inspection  # noqa: F401
import app.api.requisitos_runtime_transition  # noqa: F401

# O router de governanca e anexado ao router existente de diagramas para
# preservar o ponto unico de inclusao utilizado pelo app.main.
# O coordenador ADR/PDR é anexado ao Hub Low-Code para preservar o prefixo
# público existente sem duplicar include_router no app.main.
from app.api import (  # noqa: E402
    diagram_version_governance,
    diagramas,
    hub_lowcode,
    prompt_development_coordinator,
)

diagramas.router.include_router(diagram_version_governance.router)
hub_lowcode.router.include_router(prompt_development_coordinator.router)
