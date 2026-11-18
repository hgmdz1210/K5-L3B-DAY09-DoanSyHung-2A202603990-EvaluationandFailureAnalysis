"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    h = [x == POS for x in human]
    j = [x == POS for x in judge]
    return {"tp": sum(a and b for a, b in zip(h, j)),
            "fp": sum(b and not a for a, b in zip(h, j)),
            "fn": sum(a and not b for a, b in zip(h, j)),
            "tn": sum(not a and not b for a, b in zip(h, j))}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    c = confusion(human, judge)
    precision = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
    recall = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    c = confusion(human, judge)
    n = sum(c.values())
    if n == 0:
        raise ValueError("kappa undefined: no items")
    p_o = (c["tp"] + c["tn"]) / n
    p_e = (((c["tp"] + c["fn"]) * (c["tp"] + c["fp"])) + ((c["fp"] + c["tn"]) * (c["fn"] + c["tn"]))) / (n * n)
    if p_e == 1:
        raise ValueError("kappa undefined: chance agreement is 1 (constant labels)")
    return (p_o - p_e) / (1 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denom = sensitivity + specificity - 1
    if denom <= 0:
        raise ValueError("judge no better than chance: sensitivity + specificity <= 1")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / denom))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if x.shape != y.shape or x.ndim != 1:
        raise ValueError("paired_bootstrap needs two 1-D sequences of the same length (same items, same order)")
    if np.array_equal(x, y):
        return 0.0, 0.0, 0.0   # no difference to resample; scipy would warn on a degenerate distribution
    diff = float(x.mean() - y.mean())

    def mean_diff(u, v, axis=-1):
        return np.mean(u, axis=axis) - np.mean(v, axis=axis)

    res = bootstrap((x, y), mean_diff, paired=True, vectorized=True, n_resamples=n_resamples,
                    confidence_level=confidence, method="percentile", rng=np.random.default_rng(rng))
    return diff, float(res.confidence_interval.low), float(res.confidence_interval.high)


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    from math import comb

    _check_nck(n, c, k)
    if n - c < k:          # every k-subset contains at least one pass
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def _check_nck(n: int, c: int, k: int) -> None:
    """Reject arguments the estimators are not defined for, instead of returning a plausible number."""
    import operator

    vals = {}
    for name, v in (("n", n), ("c", c), ("k", k)):
        try:
            if isinstance(v, bool):
                raise TypeError
            vals[name] = operator.index(v)       # int, numpy int: ok; 2.0, 2.5, "2": rejected
        except TypeError:
            raise ValueError(f"{name} must be an integer, got {v!r}") from None
    n, c, k = vals["n"], vals["c"], vals["k"]
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")
    if not 0 <= c <= n:
        raise ValueError(f"c must be in [0, n={n}], got {c}")
    if not 1 <= k <= n:
        raise ValueError(f"k must be in [1, n={n}], got {k}")


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    from math import comb

    _check_nck(n, c, k)
    return comb(c, k) / comb(n, k)       # comb(c, k) == 0 when k > c
