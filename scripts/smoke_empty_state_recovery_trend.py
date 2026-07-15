#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

CARD_ID = "empty-state-recovery-trend"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--dashboard", required=True, type=Path)
    parser.add_argument("--history", required=True, type=Path)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    history = json.loads(args.history.read_text(encoding="utf-8"))

    assert report["id"] == CARD_ID
    assert report["mode"] == "advisory"
    assert report["production_blocker"] is False
    assert report["human_approval_required"] is True
    assert 0 <= report["recovery_rate"] <= 100
    assert report["average_recovery_seconds"] >= 0
    cards = dashboard.get("cards", [])
    assert sum(1 for card in cards if isinstance(card, dict) and card.get("id") == CARD_ID) == 1
    assert isinstance(history, list) and 1 <= len(history) <= 30
    assert history[-1]["recovery_rate"] == report["recovery_rate"]
    print("empty-state recovery trend smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
