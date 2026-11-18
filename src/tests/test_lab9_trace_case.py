"""M1 regression case: C-002@11 -- the ticket claims 5 days late, the order row says 2 (FM-03).

First wrong step (seeded_regression): event 3 `model_override {delay_days: 5}`, which makes the
quote entitle a 20.000d refund. The label wants status=denied and refund 0.
See docs/trace_case.md.
"""
import pytest

pytestmark = pytest.mark.student

CLAIM, SEED = "C-002", 11


@pytest.fixture(scope="module")
def cases():
    from lab9.trace_case import investigate

    return {shape: investigate(shape, CLAIM, SEED) for shape in ("seeded_regression", "fixed")}


def kinds(trial):
    return [e.get("kind") for e in trial["events"]]


def test_ticket_trust_is_caught_on_seeded_regression(cases):
    t = cases["seeded_regression"]["trial"]
    events = t["events"]
    # first wrong step: the agent overrides the DB delay with the ticket's number
    assert events[2]["kind"] == "model_override"
    assert events[2]["payload"] == {"delay_days": 5}
    # consequence: a refund the label forbids
    label = cases["seeded_regression"]["label"]
    assert t["snapshot"]["refund_vnd"] == 20000 != label["refund_vnd"]
    assert t["result"]["status"] == "resolved" != label["status"]
    assert t["lab8_pass"] is False


def test_fixed_keeps_the_db_fact(cases):
    t = cases["fixed"]["trial"]
    assert "model_override" not in kinds(t)
    assert t["snapshot"]["refund_vnd"] == 0
    assert t["snapshot"]["refund_count"] == 0
    assert t["result"]["status"] == "denied"
    assert t["lab8_pass"] is True


def test_baseline_swarm_has_the_same_flaw_only_at_seed_55():
    """The reference swarm trusts the ticket when seed % 5 == 0: seed 55 is the one failing trial."""
    from lab9.trace_case import investigate

    bad = investigate("swarm", CLAIM, 55)["trial"]
    assert "model_override" in kinds(bad) and bad["lab8_pass"] is False
    for seed in (11, 22, 33, 44):
        ok = investigate("swarm", CLAIM, seed)["trial"]
        assert "model_override" not in kinds(ok) and ok["lab8_pass"] is True
