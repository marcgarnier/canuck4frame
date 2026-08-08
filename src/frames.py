"""Map BERTopic topics to human-annotated media frames.

The manual annotation step (see PROTOCOL §7) records a `topic_id → frame_label`
mapping in ``data/results/frames_annotation.csv``. Several topics usually share a
frame (e.g. multiple mass-shooting topics → ``violence_crime``), so grouping by
frame — not by raw topic — is what turns topic modeling into framing analysis.

`topic_frame_names()` returns that mapping, falling back to BERTopic's
auto-generated topic name for any topic the annotation file does not cover (so
the pipeline still runs before annotation is done).
"""

from __future__ import annotations

import csv
from pathlib import Path

FRAMES_FILE = "frames_annotation.csv"


def load_frame_map(results_dir: str | Path | None) -> dict[int, str]:
    """Read ``frames_annotation.csv`` into a ``{topic_id: frame_label}`` dict."""
    if results_dir is None:
        return {}
    path = Path(results_dir) / FRAMES_FILE
    if not path.exists():
        return {}
    mapping: dict[int, str] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                mapping[int(row["topic_id"])] = row["frame_label"].strip()
            except (KeyError, ValueError):
                continue
    return mapping


def topic_frame_names(model, results_dir: str | Path | None = None) -> dict[int, str]:
    """topic_id → frame label (annotated) or BERTopic's auto name (fallback)."""
    info = model.get_topic_info()
    auto = dict(zip(info["Topic"], info["Name"]))
    frames = load_frame_map(results_dir)
    return {tid: frames.get(tid, name) for tid, name in auto.items()}
