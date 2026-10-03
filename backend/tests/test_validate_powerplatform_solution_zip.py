from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from scripts.validate_powerplatform_solution_zip import validate


def _package(path: Path, *, solution='ReqSysTeamsNotifications', with_flow=True):
    with ZipFile(path, 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr('solution.xml', f'<ImportExportXml><UniqueName>{solution}</UniqueName></ImportExportXml>')
        archive.writestr('customizations.xml', '<ImportExportXml />')
        if with_flow:
            archive.writestr('Workflows/robo_envia_teamsv2.json', '{}')
    return path


def test_accepts_official_solution_with_flow(tmp_path):
    package = _package(tmp_path / 'ReqSysTeamsNotifications.zip')

    result = validate(package, expected_solution='ReqSysTeamsNotifications')

    assert result['status'] == 'official_solution_valid'
    assert result['workflow_components'] == 1
    assert len(result['sha256']) == 64


def test_rejects_blueprint_without_official_root_files(tmp_path):
    package = tmp_path / 'blueprint.zip'
    with ZipFile(package, 'w') as archive:
        archive.writestr('ReqSysTeamsNotifications/manifest.json', '{}')

    with pytest.raises(ValueError, match='solution.xml'):
        validate(package, expected_solution='ReqSysTeamsNotifications')


def test_rejects_solution_without_cloud_flow(tmp_path):
    package = _package(tmp_path / 'without-flow.zip', with_flow=False)

    with pytest.raises(ValueError, match='workflow/cloud flow'):
        validate(package, expected_solution='ReqSysTeamsNotifications')


def test_rejects_wrong_solution_name(tmp_path):
    package = _package(tmp_path / 'wrong.zip', solution='AnotherSolution')

    with pytest.raises(ValueError, match='solution esperada'):
        validate(package, expected_solution='ReqSysTeamsNotifications')
