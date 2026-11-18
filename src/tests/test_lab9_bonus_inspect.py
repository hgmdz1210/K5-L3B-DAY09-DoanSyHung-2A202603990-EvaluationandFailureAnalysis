"""Bonus: the Inspect AI port agrees with pydantic-evals, and the comparison can actually fail.
Skipped unless inspect-ai is installed (pip install -r requirements-bonus.txt); CI does not install it."""
import json
import re

import pytest

pytest.importorskip("inspect_ai")
pytestmark = pytest.mark.student


@pytest.fixture
def small_spec(tmp_path):
    """3 items x 1 seed of eval set v1, incl. E-008 (seeded_regression / misreport: reply 35.000đ, ledger 20.000đ)."""
    from pathlib import Path

    from lab9 import evalset
    from lab9.eval import load_spec

    spec = load_spec(Path("config/metric_spec.yaml"))
    items = [it for it in evalset.load_jsonl(Path(spec["eval_set"])) if it["item_id"] in {"E-001", "E-008", "E-011"}]
    path = tmp_path / "eval_small.jsonl"
    path.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8")
    return {**spec, "eval_set": str(path), "seeds": [11]}


@pytest.fixture(scope="module")
def bonus():
    from lab9 import bonus_inspect, variants

    variants.register()
    bonus_inspect.register_probes()
    return bonus_inspect


@pytest.mark.parametrize("shape", ["probe_misreport", "probe_sibling_refund"])
def test_inspect_port_agrees_with_pydantic_evals(bonus, small_spec, tmp_path, shape):
    diffs, summary = bonus.compare(shape, small_spec, str(tmp_path / "logs"))
    assert diffs == []
    assert set(summary) == set(bonus.PORTED)


def test_comparison_reports_a_broken_port(bonus, small_spec, tmp_path, monkeypatch):
    # Break the Inspect reply parser only: it now sees no amounts, so the misreport goes unseen.
    monkeypatch.setattr(bonus, "_AMOUNT", re.compile(r"(?!x)x"))
    diffs, _ = bonus.compare("probe_misreport", small_spec, str(tmp_path / "logs"))
    assert any("reply_matches_ledger" in d for d in diffs)
