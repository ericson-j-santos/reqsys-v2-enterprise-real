from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class QueueCandidate:
    number: int
    created_at: str
    state: str = "open"
    base_ref: str = "main"
    mergeable: bool | None = None
    mergeable_state: str = "unknown"
    behind_by: int = 0
    checks_state: str = "missing"

    def action(self) -> str:
        if self.state != "open" or self.base_ref != "main":
            return "ignore"
        if self.mergeable is False or self.mergeable_state == "dirty":
            return "recover_conflict"
        if self.behind_by > 0:
            return "recover_behind"
        if self.checks_state == "failure":
            return "recover_ci"
        if self.checks_state in {"pending", "missing"}:
            return "wait_ci"
        if self.checks_state == "success" and self.mergeable is True:
            return "merge_candidate"
        return "inspect"

    def priority(self):
        rank = {
            "recover_conflict": 0,
            "recover_behind": 1,
            "recover_ci": 2,
            "merge_candidate": 3,
            "inspect": 4,
            "wait_ci": 5,
            "ignore": 9,
        }
        return rank[self.action()], datetime.fromisoformat(self.created_at.replace("Z", "+00:00")), self.number


def choose_candidate(candidates: list[QueueCandidate]) -> QueueCandidate | None:
    actionable = [item for item in candidates if item.action() not in {"ignore", "wait_ci"}]
    return min(actionable, key=lambda item: item.priority()) if actionable else None
