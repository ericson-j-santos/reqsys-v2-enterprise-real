"""Bootstrap do pacote de APIs."""

import app.api.copilot_studio  # noqa: F401
import app.api.requisitos_runtime_inspection  # noqa: F401
import app.api.requisitos_runtime_transition  # noqa: F401

# O router de governanca e anexado ao router existente de diagramas para
# preservar o ponto unico de inclusao utilizado pelo app.main.
from app.api import diagram_version_governance, diagramas  # noqa: E402

diagramas.router.include_router(diagram_version_governance.router)
