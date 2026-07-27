"""Statistical tests on the frame distributions.

Currently: a chi-square test of independence for whether the distribution of
frames differs between French and English coverage of 4chan.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import pandas as pd


@dataclass
class ChiSquareResult:
    chi2: float
    p_value: float
    dof: int
    n: int
    cramers_v: float          # effect size (0 = no association, 1 = perfect)
    significant: bool         # p < alpha
    alpha: float
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _topic_names(model) -> dict[int, str]:
    info = model.get_topic_info()
    return dict(zip(info["Topic"], info["Name"]))


def cramers_v(chi2: float, contingency: pd.DataFrame) -> float:
    """Bias-corrected Cramér's V effect size for a contingency table."""
    n = contingency.to_numpy().sum()
    if n == 0:
        return 0.0
    r, k = contingency.shape
    phi2 = chi2 / n
    # Bias correction (Bergsma 2013).
    phi2corr = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    rcorr = r - (r - 1) ** 2 / (n - 1)
    kcorr = k - (k - 1) ** 2 / (n - 1)
    denom = min(kcorr - 1, rcorr - 1)
    return float((phi2corr / denom) ** 0.5) if denom > 0 else 0.0


def frame_contingency(
    df: pd.DataFrame,
    topics: list[int],
    model,
    drop_outliers: bool = True,
) -> pd.DataFrame:
    """Build a language × frame count table (rows=lang, cols=frame)."""
    data = df.reset_index(drop=True).copy()
    data["topic"] = topics
    if drop_outliers:
        data = data[data["topic"] != -1]
    data["frame"] = data["topic"].map(_topic_names(model))
    return pd.crosstab(data["lang"], data["frame"])


def chi_square_fr_en(
    df: pd.DataFrame,
    topics: list[int],
    model,
    results_dir: str | Path | None = None,
    alpha: float = 0.05,
) -> ChiSquareResult:
    """Chi-square test: is frame distribution independent of language?

    Writes the contingency table and the test result to ``results_dir`` when
    provided. Warns (via ``note``) when expected cell counts are small, which
    makes the chi-square approximation unreliable for a small corpus.
    """
    from scipy.stats import chi2_contingency

    table = frame_contingency(df, topics, model)

    if table.shape[0] < 2 or table.shape[1] < 2:
        return ChiSquareResult(
            chi2=float("nan"), p_value=float("nan"), dof=0, n=int(table.to_numpy().sum()),
            cramers_v=0.0, significant=False, alpha=alpha,
            note="Need >=2 languages and >=2 frames; test not applicable.",
        )

    chi2, p, dof, expected = chi2_contingency(table)
    note = ""
    if (expected < 5).mean() > 0.2:
        note = (
            "Warning: >20% of expected cell counts are < 5 — the chi-square "
            "approximation is unreliable here; treat the p-value with caution "
            "(consider Fisher's exact test or a larger corpus)."
        )

    result = ChiSquareResult(
        chi2=float(chi2),
        p_value=float(p),
        dof=int(dof),
        n=int(table.to_numpy().sum()),
        cramers_v=cramers_v(chi2, table),
        significant=bool(p < alpha),
        alpha=alpha,
        note=note,
    )

    if results_dir is not None:
        results_dir = Path(results_dir)
        table.to_csv(results_dir / "chi2_contingency.csv")
        pd.DataFrame([result.as_dict()]).to_csv(results_dir / "chi2_fr_en_result.csv", index=False)

    return result
