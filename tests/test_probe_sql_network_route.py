from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path("scripts/probe_sql_network_route.py")
SPEC = importlib.util.spec_from_file_location("probe_sql_network_route", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_hash_is_sanitized() -> None:
    value = "CCTCODADNT013"
    digest = module._hash(value)
    assert value not in digest
    assert len(digest) == 16


@pytest.mark.parametrize("server", ["host;bad", "host/name", ""])
def test_probe_rejects_invalid_server(server: str) -> None:
    with pytest.raises(ValueError, match="invalid_server"):
        module.probe(server)


@pytest.mark.parametrize("port", [0, 65536])
def test_probe_rejects_invalid_port(port: int) -> None:
    with pytest.raises(ValueError, match="invalid_port"):
        module.probe("localhost", port=port)
