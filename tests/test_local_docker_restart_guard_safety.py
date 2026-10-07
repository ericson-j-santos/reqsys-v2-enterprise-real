from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "script_name",
    [
        "agendar-subida-stack-docker.ps1",
        "reiniciar-docker-seguro.ps1",
        "reiniciar-stack-limpo.ps1",
        "subir-stack-sem-colisao.ps1",
    ],
)
def test_windows_entrypoints_use_canonical_project_dir_from_preflight(
    script_name: str,
) -> None:
    script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")

    capture = re.search(
        r"\$preflight\s*=\s*&\s*\$preflightScript\b[^\r\n]*",
        script,
        flags=re.IGNORECASE,
    )
    assignment = re.search(
        r"\$ProjetoDir\s*=\s*\$preflight\.ProjetoDir\b",
        script,
        flags=re.IGNORECASE,
    )

    assert capture is not None
    assert assignment is not None
    assert capture.start() < assignment.start()
    assert "| Out-Null" not in capture.group(0)


def test_scheduler_resolves_target_script_after_project_canonicalization() -> None:
    script = (ROOT / "scripts" / "agendar-subida-stack-docker.ps1").read_text(
        encoding="utf-8"
    )

    canonical = "$ProjetoDir = $preflight.ProjetoDir"
    target_script = (
        "$subirScript = Join-Path $ProjetoDir "
        "'scripts\\subir-stack-sem-colisao.ps1'"
    )
    validation = "Test-Path -LiteralPath $subirScript -PathType Leaf"

    assert canonical in script
    assert target_script in script
    assert validation in script
    assert script.index(canonical) < script.index(target_script)
    assert script.index(target_script) < script.index(validation)


def test_ssrs_restart_reuses_canonical_project_root_from_preflight() -> None:
    script = (ROOT / "scripts" / "configurar-ssrs.ps1").read_text(
        encoding="utf-8"
    )

    capture = "$preflight = & $preflightScript -ProjetoDir $projectRoot"
    assignment = "$projectRoot = $preflight.ProjetoDir"

    assert capture in script
    assert assignment in script
    assert script.index(capture) < script.index(assignment)


def test_clean_restart_requires_explicit_destructive_consent() -> None:
    script = (ROOT / "scripts" / "reiniciar-stack-limpo.ps1").read_text(
        encoding="utf-8"
    )

    assert "SupportsShouldProcess = $true" in script
    assert "ConfirmImpact = 'High'" in script
    assert "[switch]$RemoverVolumes" in script
    assert "if (-not $RemoverVolumes)" in script
    assert "$PSCmdlet.ShouldProcess" in script
    assert script.index("if (-not $RemoverVolumes)") < script.index("down -v")
    assert script.index("$PSCmdlet.ShouldProcess") < script.index("down -v")


def test_clean_restart_checks_compose_working_dir_before_volume_removal() -> None:
    script = (ROOT / "scripts" / "reiniciar-stack-limpo.ps1").read_text(
        encoding="utf-8"
    )

    guard = "Assert-ComposeWorkingDirectory -ProjectName"
    label = "com.docker.compose.project.working_dir"

    assert 'label=com.docker.compose.project=$ProjectName' in script
    assert label in script
    assert "[System.StringComparison]::OrdinalIgnoreCase" in script
    assert "Nao ha containers" in script
    assert "pertence a outra copia" in script
    assert script.index(guard) < script.index("down -v")
