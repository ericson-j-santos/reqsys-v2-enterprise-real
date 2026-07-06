"""API package bootstrap.

Importa extensões de router com efeitos controlados antes do registro final em
`app.main`.
"""

from app.api import requisitos_runtime_transition  # noqa: F401
