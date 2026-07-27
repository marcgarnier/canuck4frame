"""Unit tests for the chi-square / effect-size helpers.

These use a fake model + tiny DataFrame so they run without the ML stack
(beyond scipy), keeping CI fast.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import stats  # noqa: E402


class _FakeModel:
    """Minimal stand-in exposing get_topic_info() like BERTopic does."""

    def __init__(self, names):
        self._names = names

    def get_topic_info(self):
        return pd.DataFrame({"Topic": list(self._names), "Name": list(self._names.values())})


def _frame(lang_topic_pairs):
    return pd.DataFrame(
        {
            "lang": [lt[0] for lt in lang_topic_pairs],
            "text": ["doc"] * len(lang_topic_pairs),
        }
    ), [lt[1] for lt in lang_topic_pairs]


def test_contingency_drops_outliers():
    model = _FakeModel({0: "A", 1: "B"})
    df, topics = _frame([("en", 0), ("fr", 1), ("en", -1)])
    table = stats.frame_contingency(df, topics, model)
    assert table.to_numpy().sum() == 2  # the -1 outlier is dropped


def test_chi_square_detects_strong_association():
    # EN is entirely frame A, FR entirely frame B -> maximal association.
    model = _FakeModel({0: "A", 1: "B"})
    pairs = [("en", 0)] * 20 + [("fr", 1)] * 20
    df, topics = _frame(pairs)
    res = stats.chi_square_fr_en(df, topics, model)
    assert res.significant is True
    assert res.p_value < 0.05
    assert res.cramers_v > 0.5


def test_chi_square_independent_distribution():
    # Same 50/50 frame mix in both languages -> no association.
    model = _FakeModel({0: "A", 1: "B"})
    pairs = ([("en", 0)] * 15 + [("en", 1)] * 15 + [("fr", 0)] * 15 + [("fr", 1)] * 15)
    df, topics = _frame(pairs)
    res = stats.chi_square_fr_en(df, topics, model)
    assert res.significant is False
    assert res.cramers_v < 0.2


def test_chi_square_not_applicable_single_frame():
    model = _FakeModel({0: "A"})
    df, topics = _frame([("en", 0), ("fr", 0)])
    res = stats.chi_square_fr_en(df, topics, model)
    assert res.significant is False
    assert "not applicable" in res.note


def test_small_counts_trigger_warning():
    model = _FakeModel({0: "A", 1: "B"})
    df, topics = _frame([("en", 0), ("fr", 1), ("en", 1), ("fr", 0)])
    res = stats.chi_square_fr_en(df, topics, model)
    assert "expected cell counts" in res.note
