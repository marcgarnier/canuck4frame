"""End-to-end Canuck4Frame pipeline runner.

Examples
--------
Collect the corpus (per config.yaml backend), then run the full analysis:
    python scripts/run_pipeline.py --collect

Re-run only modeling + analysis on an already-collected corpus:
    python scripts/run_pipeline.py --skip-collect
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a plain script (python scripts/run_pipeline.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import collect as collect_mod  # noqa: E402
from src import modeling, preprocess, stats, visualization  # noqa: E402
from src.config import load_config  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Canuck4Frame pipeline.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--collect", action="store_true", help="Collect fresh data (per config backend).")
    group.add_argument("--skip-collect", action="store_true", help="Reuse an existing raw corpus.")
    args = parser.parse_args()

    config = load_config()
    results = config["paths"]["results"]

    # --- 1. Data ----------------------------------------------------------
    if not args.skip_collect:
        collect_mod.collect(config)

    # --- 2. Preprocess ----------------------------------------------------
    print("\n== Preprocessing ==")
    written = preprocess.preprocess(config)

    import pandas as pd

    df = pd.read_csv(written["all"], parse_dates=["date"])
    print(f"Corpus ready: {len(df)} articles")

    # --- 3. Model ---------------------------------------------------------
    print("\n== BERTopic modeling ==")
    model, topics, _ = modeling.fit_model(config, df)
    modeling.topic_summary(model).to_csv(results / "topic_summary.csv", index=False)
    modeling.save_model(model, results / "bertopic_model")

    # --- 4. Visualize -----------------------------------------------------
    print("\n== Visualization ==")
    visualization.frames_over_time(model, df, topics, results)
    visualization.compare_fr_en(df, topics, model, results)

    # Chi-square: is frame distribution independent of language?
    chi = stats.chi_square_fr_en(df, topics, model, results)
    print(f"  chi2={chi.chi2:.2f}, p={chi.p_value:.4f}, "
          f"Cramér's V={chi.cramers_v:.2f}, significant={chi.significant}")
    if chi.note:
        print(f"  {chi.note}")
    try:
        visualization.wordclouds(model, results)
        visualization.topics_over_time_interactive(model, df, results)
    except Exception as exc:  # optional extras shouldn't fail the run
        print(f"  (skipped optional visuals: {exc})")

    print(f"\nDone. Artifacts written to {results}")


if __name__ == "__main__":
    main()
