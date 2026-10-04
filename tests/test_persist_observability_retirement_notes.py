from scripts.persist_observability_e2e_evidence import _operational_notes


def test_failed_precondition_has_provider_neutral_note():
    notes = _operational_notes({"gate_passed": False, "precondition_ok": False})
    assert notes[0]["id"] == "runtime_precondition_failed"
    assert notes[0]["scope"] == "observability_e2e"
    assert "next_increment" not in notes[0]
    assert "fly" not in str(notes).lower()
