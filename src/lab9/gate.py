"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    for side, rep in (("pr", pr), ("baseline", base)):
        problems += [f"{side}: {p}" for p in _report_problems(rep, spec)]
    problems += _pair_problems(pr, base)
    if base_spec is not None:
        problems += ratchet_problems(spec, base_spec)
    return problems


def _is_bad_number(v) -> bool:
    return isinstance(v, float) and (math.isnan(v) or math.isinf(v))


def _report_problems(rep: dict, spec: dict) -> list[str]:
    """Checks one report can fail on its own."""
    out: list[str] = []
    man, rows = rep.get("manifest") or {}, rep.get("rows")
    if not isinstance(rows, list) or not rows:
        return ["no rows"]
    for k, v in (rep.get("metrics") or {}).items():
        if _is_bad_number(v):
            out.append(f"metric {k} is {v} (a crashed grader or a NaN mean)")
    if "evaluator_failures" not in rep:
        out.append("evaluator_failures field missing")
    elif rep["evaluator_failures"]:
        out.append(f"{len(rep['evaluator_failures'])} evaluator failure(s), first: {rep['evaluator_failures'][0]}")
    want = (man.get("items") or 0) * len(man.get("seeds") or [])
    if len(rows) != want:
        out.append(f"{len(rows)} rows, manifest says {man.get('items')} item x {len(man.get('seeds') or [])} seed = {want}")
    keys = [(r.get("item_id"), r.get("seed")) for r in rows]
    dupes = sorted({k for k in keys if keys.count(k) > 1}, key=str)
    if dupes:
        out.append(f"duplicated (item, seed) rows: {dupes[:5]}")
    if spec.get("seeds") is not None and list(man.get("seeds") or []) != list(spec["seeds"]):
        out.append(f"manifest seeds {man.get('seeds')} != spec seeds {spec['seeds']}")
    graded = [m["id"] for m in spec.get("metrics", []) if m["id"] in GRADERS]
    for m in graded:
        missing = [f"{r.get('item_id')}@{r.get('seed')}" for r in rows if r.get(m) is None or _is_bad_number(r.get(m))]
        if missing:
            out.append(f"metric {m} has no value on {len(missing)} row(s), first {missing[0]} (crashed grader?)")
    tags: dict[str, set] = {}
    for r in rows:
        tags.setdefault(r.get("item_id"), set()).add(tuple(sorted(r.get("slices") or [])))
    out += [f"item {i} carries different slice tags across seeds" for i, t in tags.items() if len(t) > 1]
    # The reported metrics must be what the rows say: a hand-edited summary is not evidence.
    if not out and all("cost" in r for r in rows):
        ids = [m for m in graded if m in rows[0]]
        again = aggregate(rows, ids, k_values=spec.get("pass_k", []))
        for k, v in again.items():
            got = (rep.get("metrics") or {}).get(k)
            if k in (rep.get("metrics") or {}) and not _same_number(got, v):
                out.append(f"metric {k} reported {got} but the rows give {v} (edited by hand?)")
    return out


def _same_number(a, b) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return abs(float(a) - float(b)) <= 1e-9
    except (TypeError, ValueError):
        return False


def _pair_problems(pr: dict, base: dict) -> list[str]:
    """PR and baseline must cover the same (item, seed) trials with the same slice tags."""
    out: list[str] = []
    a = {(r.get("item_id"), r.get("seed")) for r in pr.get("rows") or []}
    b = {(r.get("item_id"), r.get("seed")) for r in base.get("rows") or []}
    if a != b:
        out.append(f"(item, seed) set differs from the baseline: {len(b - a)} missing, {len(a - b)} extra"
                   f" (e.g. missing {sorted(b - a, key=str)[:3]})")
    ta = {r.get("item_id"): sorted(r.get("slices") or []) for r in pr.get("rows") or []}
    tb = {r.get("item_id"): sorted(r.get("slices") or []) for r in base.get("rows") or []}
    for item in sorted(set(ta) & set(tb), key=str):
        if ta[item] != tb[item]:
            out.append(f"item {item} slice tags {ta[item]} != baseline {tb[item]} (relabelled out of a slice?)")
    return out


def ratchet_problems(spec: dict, base_spec: dict) -> list[str]:
    """Same eval-set version => thresholds may only get stricter. Anything looser is a problem."""
    if (spec.get("eval_set_version") != base_spec.get("eval_set_version")
            and spec.get("eval_set") != base_spec.get("eval_set")):
        return []   # a genuinely new eval set starts a new ratchet (and needs a new baseline)
    # Bumping the version label while pointing at the same eval set is not a new eval set.
    out: list[str] = []
    for k in ("eval_set", "labels", "adversarial_pack"):
        if base_spec.get(k) != spec.get(k):
            out.append(f"ratchet: {k} changed from {base_spec.get(k)!r} to {spec.get(k)!r} on the same eval-set version")
    if list(base_spec.get("seeds") or []) != list(spec.get("seeds") or []):
        out.append(f"ratchet: seeds changed from {base_spec.get('seeds')} to {spec.get('seeds')}")
    bc = (base_spec.get("bootstrap") or {}).get("confidence")
    sc = (spec.get("bootstrap") or {}).get("confidence")
    if bc is not None and (sc is None or sc < bc):
        out.append(f"ratchet: bootstrap confidence lowered from {bc} to {sc}")
    new = {m["id"]: m for m in spec.get("metrics") or []}
    for m in base_spec.get("metrics") or []:
        if m["id"] not in new:
            out.append(f"ratchet: metric {m['id']} was removed")
            continue
        out += [f"ratchet: metric {m['id']} {p}" for p in _looser(m.get("threshold") or {}, new[m["id"]].get("threshold") or {},
                                                                 m.get("blocking"), new[m["id"]].get("blocking"))]
    new_sl = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        key = (s["name"], s["metric"])
        if key not in new_sl:
            out.append(f"ratchet: slice {key[0]}/{key[1]} was removed")
            continue
        out += [f"ratchet: slice {key[0]}/{key[1]} {p}" for p in _looser(s, new_sl[key], s.get("blocking"),
                                                                       new_sl[key].get("blocking"))]
    return out


def _looser(old: dict, new: dict, old_blocking, new_blocking) -> list[str]:
    out = []
    if old_blocking and not new_blocking:
        out.append("is no longer blocking")
    for k in ("max", "max_increase"):
        if k in old and (k not in new or new[k] > old[k]):
            out.append(f"{k} raised from {old[k]} to {new.get(k)}")
    if "min" in old and ("min" not in new or new["min"] < old["min"]):
        out.append(f"min lowered from {old['min']} to {new.get('min')}")
    if old.get("no_significant_drop") and not new.get("no_significant_drop"):
        out.append("dropped no_significant_drop")
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices") or []:
        name, metric = sl["name"], sl["metric"]
        sid = f"slice:{name}/{metric}"
        a, b = per_item(pr, metric, slice_name=name), per_item(base, metric, slice_name=name)
        verdict, note, val = "ok", "", None
        if not a:
            # An empty slice cannot vouch for anything: a relabelled or dropped slice must not pass.
            verdict = "missing"
        else:
            val = round(sum(a.values()) / len(a), 4)
            if "min" in sl and val < sl["min"]:
                verdict = "fail"
            if sl.get("no_significant_drop"):
                keys = sorted(set(a) & set(b))
                if keys:
                    d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                       n_resamples=bs.get("n_resamples", 1000),
                                                       rng=bs.get("rng", 2027))
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = "fail"
                else:
                    verdict = "missing"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if sl.get("blocking") else "warn")
        th = {k: sl[k] for k in ("min", "no_significant_drop") if k in sl}
        lines.append(f"  {sid:<34} {val!s:<8} n={len(a):<3} {json.dumps(th):<36} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
