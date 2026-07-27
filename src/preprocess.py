"""Cleaning and language separation for the raw corpus.

Turns the raw JSONL produced by ``collect`` into tidy CSV files ready for
BERTopic:

    data/processed/articles_all.csv   (everything, with a `lang` column)
    data/processed/articles_en.csv    (English sub-corpus)
    data/processed/articles_fr.csv    (French sub-corpus)

Design choices worth flagging:
  * Accents are preserved (they matter for French).
  * We do NOT lowercase or strip stopwords here — BERTopic's embedding model
    wants natural text, and stopword handling happens inside the c-TF-IDF
    vectorizer at modeling time (see ``modeling.build_vectorizer``).
  * Language is detected per-article with langdetect and only falls back to the
    outlet hint when detection is uncertain.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from langdetect import DetectorFactory, LangDetectException, detect

# Make langdetect deterministic (reproducibility).
DetectorFactory.seed = 0

_WS = re.compile(r"\s+")
_BOILERPLATE = re.compile(
    r"(social sharing|©|all rights reserved|abonnez-vous|sign up for|"
    r"newsletter|cookie|subscribe now)",
    re.IGNORECASE,
)


def clean_text(text: str | None) -> str:
    """Collapse whitespace and drop obvious boilerplate lines."""
    if not text:
        return ""
    lines = [ln for ln in text.splitlines() if not _BOILERPLATE.search(ln)]
    return _WS.sub(" ", " ".join(lines)).strip()


def detect_language(text: str, fallback: str = "unknown") -> str:
    try:
        code = detect(text)
    except LangDetectException:
        return fallback
    return code if code in {"en", "fr"} else fallback


def load_raw(raw_path: str | Path) -> pd.DataFrame:
    """Read the newline-delimited JSON corpus into a DataFrame."""
    rows = []
    with open(raw_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def preprocess(config: dict, raw_path: str | Path | None = None) -> dict[str, Path]:
    """Clean, deduplicate, language-tag, and split the corpus.

    Returns a dict of written paths keyed by ``all`` / ``en`` / ``fr``.
    """
    paths = config["paths"]
    pp = config["preprocess"]
    raw_path = Path(raw_path) if raw_path else paths["raw"] / "articles_raw.jsonl"

    df = load_raw(raw_path)
    if df.empty:
        raise ValueError(f"No articles found in {raw_path}. Run collection first.")

    # 1. Clean body + title.
    df["body"] = df["body"].apply(clean_text)
    df["title"] = df["title"].fillna("").apply(clean_text)
    df["text"] = (df["title"] + ". " + df["body"]).str.strip()

    # 2. Drop empties, stubs, and duplicates.
    df = df[df["body"].str.len() >= pp["min_chars"]]
    df = df.drop_duplicates(subset="url").drop_duplicates(subset="text")
    df = df.reset_index(drop=True)

    # 3. Detect language per article (fall back to the outlet hint).
    df["lang"] = df.apply(
        lambda r: detect_language(r["text"], fallback=r.get("lang", "unknown")),
        axis=1,
    )

    # 4. Parse dates + derive a `year` column for temporal analysis.
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["year"] = df["date"].dt.year

    # 5. Persist.
    cols = ["id", "title", "body", "text", "date", "year", "source", "domain", "lang", "url"]
    df = df[[c for c in cols if c in df.columns]]

    written: dict[str, Path] = {}
    all_path = paths["processed"] / "articles_all.csv"
    df.to_csv(all_path, index=False)
    written["all"] = all_path

    for code in ("en", "fr"):
        sub = df[df["lang"] == code]
        p = paths["processed"] / f"articles_{code}.csv"
        sub.to_csv(p, index=False)
        written[code] = p
        print(f"  {code}: {len(sub)} articles")

    print(f"  total: {len(df)} articles -> {all_path}")
    return written
