from scripts.governed_pr_queue_controller import QueueCandidate, choose_candidate


def c(number, created, **kwargs):
    return QueueCandidate(number=number, created_at=created, **kwargs)


def test_conflict_is_actionable_without_ci_failure():
    assert c(44, "2026-06-01T00:00:00Z", mergeable=False, mergeable_state="dirty").action() == "recover_conflict"


def test_behind_is_actionable_even_with_green_ci():
    assert c(58, "2026-06-02T00:00:00Z", mergeable=True, behind_by=5, checks_state="success").action() == "recover_behind"


def test_ci_failure_is_actionable_after_mergeability():
    assert c(73, "2026-06-03T00:00:00Z", mergeable=True, checks_state="failure").action() == "recover_ci"


def test_priority_is_conflict_then_behind_then_ci():
    items = [
        c(73, "2026-06-01T00:00:00Z", mergeable=True, checks_state="failure"),
        c(58, "2026-06-02T00:00:00Z", mergeable=True, behind_by=2, checks_state="success"),
        c(81, "2026-06-03T00:00:00Z", mergeable=False, mergeable_state="dirty"),
    ]
    assert choose_candidate(items).number == 81


def test_oldest_wins_inside_same_action_class():
    items = [
        c(74, "2026-06-04T00:00:00Z", mergeable=False, mergeable_state="dirty"),
        c(44, "2026-06-01T00:00:00Z", mergeable=False, mergeable_state="dirty"),
    ]
    assert choose_candidate(items).number == 44


def test_pending_only_does_not_create_action():
    assert choose_candidate([c(90, "2026-06-05T00:00:00Z", mergeable=True, checks_state="pending")]) is None
