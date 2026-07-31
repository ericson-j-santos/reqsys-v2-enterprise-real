from pathlib import Path


def test_architecture_flow_keeps_bacen_between_stg_and_prod() -> None:
    diagram = Path("docs/architecture/fly-automatic-promotion-flow.md").read_text(
        encoding="utf-8"
    )
    assert "SOK --> BACEN" in diagram
    assert "BACEN -->|autorizado| CPROD" in diagram
    assert "BACEN -->|bloqueado| STOP" in diagram
