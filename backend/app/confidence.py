"""Calibrated relevance confidence for retrieved courses.

A small logistic model maps three retrieval signals to an estimated probability that a result is relevant:
  sim     cosine similarity between the query and the course embedding
  sem_rr  reciprocal of the course's rank in the semantic channel (0 when that channel did not return it)
  both    1 when both the keyword and the semantic channel retrieved the course
It is fitted on the labelled evaluation pool (data/evaluation/judgments.json) by scripts/evaluate.py, which also
scores it with leave-one-query-out cross-validation, so the reported calibration quality is measured on queries the
model did not see. The feature set was picked from a handful of candidates on that same cross-validation, so its
figures are slightly optimistic. Keyword-overlap features did not beat the base rate and are shown, not modelled.
Keyword-only mode has no semantic signal, so its "model" is the labelled base rate alone.
The model only annotates results; it never changes the ranking.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

FEATURES = {"hybrid": ["sim", "sem_rr", "both"], "keyword_only": []}
L2 = 1.0  # ridge penalty on the weights (not the intercept); keeps 187 labels from over-fitting
BINS = (0.0, 0.25, 0.5, 0.75, 1.0)


def features(sim: float | None, semantic_rank: int | None, both: bool) -> dict[str, float]:
    return {"sim": 0.0 if sim is None else float(sim), "sem_rr": 1.0 / semantic_rank if semantic_rank else 0.0,
            "both": 1.0 if both else 0.0}


def _matrix(rows: list[dict[str, float]], names: list[str]) -> np.ndarray:
    return np.array([[1.0] + [r[n] for n in names] for r in rows], dtype=np.float64)


def fit(rows: list[dict[str, float]], labels: list[bool], names: list[str]) -> np.ndarray:
    """Ridge-penalised logistic regression by Newton's method (IRLS). Returns [intercept, *weights]."""
    x, y = _matrix(rows, names), np.array(labels, dtype=np.float64)
    w = np.zeros(x.shape[1])
    penalty = np.diag([0.0] + [L2] * len(names))
    for _ in range(50):
        p = 1.0 / (1.0 + np.exp(-(x @ w)))
        grad = x.T @ (p - y) + penalty @ w
        hess = x.T @ (x * (p * (1 - p))[:, None]) + penalty
        step = np.linalg.solve(hess, grad)
        w -= step
        if np.abs(step).max() < 1e-9:
            break
    return w


def predict(w: np.ndarray | list[float], row: dict[str, float], names: list[str]) -> float:
    z = w[0] + sum(wi * row[n] for wi, n in zip(w[1:], names))
    return 1.0 / (1.0 + math.exp(-z))


def _auc(scores: list[float], labels: list[bool]) -> float | None:
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def cross_validate(groups: list[str], rows: list[dict[str, float]], labels: list[bool], names: list[str]) -> dict[str, Any]:
    """Leave-one-query-out: each query's labels are predicted by a model fitted on the other queries."""
    preds, base_preds = [0.0] * len(rows), [0.0] * len(rows)
    for g in dict.fromkeys(groups):
        train = [i for i, q in enumerate(groups) if q != g]
        w = fit([rows[i] for i in train], [labels[i] for i in train], names)
        base = sum(labels[i] for i in train) / len(train)
        for i, q in enumerate(groups):
            if q == g:
                preds[i], base_preds[i] = predict(w, rows[i], names), base
    y = np.array(labels, dtype=np.float64)
    p, b = np.array(preds), np.array(base_preds)
    eps = 1e-12
    bins = []
    for lo, hi in zip(BINS, BINS[1:]):
        idx = [i for i, v in enumerate(preds) if lo <= v < hi or (hi == 1.0 and v == 1.0)]
        if idx:
            bins.append({"lo": lo, "hi": hi, "n": len(idx), "predicted": round(float(p[idx].mean()), 3),
                         "observed": round(float(y[idx].mean()), 3)})
    return {
        "brier": round(float(((p - y) ** 2).mean()), 4),
        "baseline_brier": round(float(((b - y) ** 2).mean()), 4),
        "log_loss": round(float(-(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)).mean()), 4),
        "accuracy": round(float(((p >= 0.5) == (y == 1)).mean()), 3),
        # A constant model (no features) ranks nothing; its fold-to-fold base rates would fake an AUC.
        "auc": None if not names or (a := _auc(preds, labels)) is None else round(a, 3),
        "reliability": bins,
    }


class Calibration:
    """Loaded at startup from calibration.json; absent file means no confidence is shown."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.models = data["models"]

    @classmethod
    def load(cls, path: Path) -> "Calibration | None":
        if not path.exists():
            return None
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def model(self, mode: str) -> dict[str, Any] | None:
        m = self.models.get(mode)
        # A file written for another feature set is stale: show no confidence rather than a wrong one.
        return m if m is not None and m["features"] == FEATURES.get(mode) else None

    def probability(self, mode: str, row: dict[str, float]) -> float | None:
        m = self.model(mode)
        return None if m is None else predict(m["weights"], row, m["features"])


def band(p: float | None) -> str | None:
    if p is None:
        return None
    return "high" if p >= 0.75 else "medium" if p >= 0.5 else "low"
