"""M7 extra traps beyond lab9.traps (hints in CHECKPOINTS: duplicated rows, evaluator failures on a
green run) plus relabelled slices, hand-edited metrics and a version bump that dodges the ratchet.
Each builds a gamed report from a small honest one; integrity_check must flag every one."""
import copy

import pytest

pytestmark = pytest.mark.student

SEEDS = (1, 2)
SPEC = {"eval_set_version": "v2", "eval_set": "data/eval/eval_set_v2.jsonl", "seeds": list(SEEDS),
        "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                     "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9, "blocking": True}]}


def _honest(fail=()):
    from lab9.eval import aggregate

    rows = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": (i, s) not in fail,
             "slices": ["money_movement"] if i < 2 else [], "cost": 1.0}
            for i in range(4) for s in SEEDS]
    return {"manifest": {"eval_set_sha": "x", "items": 4, "seeds": list(SEEDS)}, "rows": rows,
            "metrics": aggregate(rows, ["pass_rate"]), "evaluator_failures": []}


@pytest.fixture(scope="module")
def gate():
    from lab9 import gate

    return gate


def test_honest_reports_pass(gate):
    base = _honest()
    assert gate.integrity_check(base, base, SPEC) == []
    assert gate.integrity_check(_honest(fail={(0, 1)}), base, SPEC, SPEC) == []


def test_duplicated_rows_hiding_a_failure(gate):
    pr = _honest(fail={(0, 1)})
    good = next(r for r in pr["rows"] if r["pass_rate"])
    pr["rows"] = [copy.deepcopy(good) if not r["pass_rate"] else r for r in pr["rows"]]   # same count
    assert gate.integrity_check(pr, _honest(), SPEC)


def test_evaluator_failures_on_a_green_run(gate):
    pr = _honest()
    pr["evaluator_failures"] = ["E-001@1:ReplyMatchesLedger:KeyError"]
    assert gate.integrity_check(pr, _honest(), SPEC)


def test_item_relabelled_out_of_a_slice(gate):
    pr = _honest(fail={(0, 1), (0, 2)})
    for r in pr["rows"]:
        if r["item_id"] == "E-000":
            r["slices"] = []
    assert gate.integrity_check(pr, _honest(), SPEC)


def test_hand_edited_summary_metric(gate):
    pr = _honest(fail={(0, 1), (1, 1), (2, 1)})
    pr["metrics"]["pass_rate"] = 1.0
    assert gate.integrity_check(pr, _honest(), SPEC)


def test_version_bump_on_the_same_eval_set_still_ratchets(gate):
    loose = copy.deepcopy(SPEC)
    loose["eval_set_version"] = "v2.1"
    loose["metrics"][0]["threshold"]["min"] = 0.5
    assert gate.integrity_check(_honest(), _honest(), loose, SPEC)


def test_slice_dropped_or_made_non_blocking(gate):
    for change in ({"slices": []}, {"slices": [dict(SPEC["slices"][0], blocking=False)]}):
        assert gate.integrity_check(_honest(), _honest(), dict(SPEC, **change), SPEC)


def test_stricter_spec_is_allowed(gate):
    strict = copy.deepcopy(SPEC)
    strict["metrics"][0]["threshold"]["min"] = 0.9
    strict["slices"][0]["min"] = 0.95
    assert gate.integrity_check(_honest(), _honest(), strict, SPEC) == []
