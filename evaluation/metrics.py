from __future__ import annotations
import math
import statistics


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0}


def rate(k, n):
    """Proportion with Wilson 95% interval (small samples => wide intervals)."""
    if n == 0:
        return {"value": None, "k": k, "n": n, "ci95": None}
    z, p = 1.96, k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {"value": round(p, 4), "k": k, "n": n, "ci95": [round(max(0, c - h), 4), round(min(1, c + h), 4)]}


def median(xs):
    return statistics.median(xs) if xs else None
