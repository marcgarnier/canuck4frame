"""Temporal, comparative, and descriptive visualizations of the frames.

All functions take a fitted BERTopic ``model`` and the aligned DataFrame (same
row order as the documents passed to ``fit_transform``) plus the ``topics``
list, and write PNG/HTML/CSV artifacts into ``data/results``.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .frames import topic_frame_names

sns.set_theme(style="whitegrid")


def _attach_topics(df: pd.DataFrame, topics: list[int]) -> pd.DataFrame:
    out = df.reset_index(drop=True).copy()
    out["topic"] = topics
    return out


def frames_over_time(
    model,
    df: pd.DataFrame,
    topics: list[int],
    results_dir: str | Path,
    drop_outliers: bool = True,
) -> pd.DataFrame:
    """Proportion of articles per frame per year -> CSV + stacked-area PNG."""
    results_dir = Path(results_dir)
    data = _attach_topics(df, topics)
    if drop_outliers:
        data = data[data["topic"] != -1]

    name_map = topic_frame_names(model, results_dir)
    data["frame"] = data["topic"].map(name_map)

    counts = data.groupby(["year", "frame"]).size().unstack(fill_value=0)
    proportions = counts.div(counts.sum(axis=1), axis=0)

    counts.to_csv(results_dir / "temporal_counts.csv")
    proportions.to_csv(results_dir / "temporal_analysis.csv")

    ax = proportions.plot.area(figsize=(11, 6), colormap="tab20", alpha=0.85)
    ax.set_title("Media frames of 4chan over time (share of articles per year)")
    ax.set_ylabel("Share of articles")
    ax.set_xlabel("Year")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    plt.tight_layout()
    plt.savefig(results_dir / "frames_over_time.png", dpi=150)
    plt.close()
    return proportions


def topics_over_time_interactive(
    model,
    df: pd.DataFrame,
    results_dir: str | Path,
) -> None:
    """BERTopic's native keyword-evolution chart, saved as interactive HTML."""
    results_dir = Path(results_dir)
    timestamps = pd.to_datetime(df["date"]).tolist()
    tot = model.topics_over_time(df["text"].tolist(), timestamps, nr_bins=min(20, df["year"].nunique() or 1))
    fig = model.visualize_topics_over_time(tot, top_n_topics=10)
    fig.write_html(str(results_dir / "topics_over_time.html"))


def compare_fr_en(
    df: pd.DataFrame,
    topics: list[int],
    model,
    results_dir: str | Path,
) -> pd.DataFrame:
    """Frame distribution FR vs EN -> CSV + grouped bar chart (unified model)."""
    results_dir = Path(results_dir)
    data = _attach_topics(df, topics)
    data = data[data["topic"] != -1]
    data["frame"] = data["topic"].map(topic_frame_names(model, results_dir))

    table = (
        data.groupby(["lang", "frame"]).size().unstack(fill_value=0).T
    )
    share = table.div(table.sum(axis=0), axis=1)  # column-normalized per language
    share.to_csv(results_dir / "comparative_fr_en.csv")

    ax = share.plot.bar(figsize=(11, 6))
    ax.set_title("Frame distribution: French vs English coverage of 4chan")
    ax.set_ylabel("Share within language")
    ax.set_xlabel("Frame")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(results_dir / "comparative_fr_en.png", dpi=150)
    plt.close()
    return share


def wordclouds(model, results_dir: str | Path, top_n_topics: int = 8) -> None:
    """One word cloud per frame (optional, descriptive)."""
    from wordcloud import WordCloud

    results_dir = Path(results_dir)
    info = model.get_topic_info()
    topic_ids = [t for t in info["Topic"].tolist() if t != -1][:top_n_topics]
    if not topic_ids:
        return

    cols = 3
    rows = (len(topic_ids) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 3 * rows))
    for ax, tid in zip(axes.ravel(), topic_ids):
        freqs = dict(model.get_topic(tid))
        wc = WordCloud(width=400, height=300, background_color="white").generate_from_frequencies(freqs)
        ax.imshow(wc, interpolation="bilinear")
        ax.set_title(topic_frame_names(model, results_dir).get(tid, str(tid)), fontsize=9)
        ax.axis("off")
    for ax in axes.ravel()[len(topic_ids):]:
        ax.axis("off")
    plt.tight_layout()
    plt.savefig(results_dir / "frame_wordclouds.png", dpi=150)
    plt.close()
