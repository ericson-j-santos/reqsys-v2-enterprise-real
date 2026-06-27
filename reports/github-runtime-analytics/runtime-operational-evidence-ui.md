# Runtime Operational Evidence UI

| Field | Value |
|---|---:|
| Readiness | Runtime evidence graph consolidated |
| Status color | green |
| Runtime state | EVIDENCE_GRAPH_READY |
| Nodes | 3 |
| Edges | 2 |
| Confidence | 93% |
| Risk | 4% |

## Navigable graph nodes

| Node | Label | Correlation | State | Color |
|---|---|---|---|---|
| `event_1` | pull_request_state_captured | operational | review_only | green |
| `event_2` | github_actions_state_captured | ci | review_only | green |
| `event_3` | governance_gate_state_captured | governance | review_only | green |

## Temporal correlations

| From | To | Type |
|---|---|---|
| `event_1` | `event_2` | temporal_correlation |
| `event_2` | `event_3` | temporal_correlation |

## Guardrail

This artifact is `review_only` and does not authorize production decisions without human governance review.
