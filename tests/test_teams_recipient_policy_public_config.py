from __future__ import annotations

import json
from pathlib import Path


CONFIG = Path("governance/notifications/teams-recipient-policies.json")


def test_public_policy_file_contains_no_recipient_identity() -> None:
    document = json.loads(CONFIG.read_text(encoding="utf-8"))

    assert document["schema_version"] == "1.1.0"
    assert document["policies"]

    serialized = CONFIG.read_text(encoding="utf-8")
    assert "@" not in serialized

    for policy in document["policies"]:
        assert policy["recipient_source"] == "runtime_db"
        assert policy["recipients"] == []
