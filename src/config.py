"""Configuration loading and path helpers.

A single ``config.yaml`` at the repository root drives every script and
notebook, so parameters (date range, outlets, model hyper-parameters) live in
one place and the pipeline stays reproducible.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Repository root = parent of the directory containing this file.
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load ``config.yaml`` and environment variables from ``.env``.

    Relative paths under the ``paths`` section are resolved to absolute paths
    (anchored at the repo root) and the referenced directories are created.
    """
    load_dotenv(ROOT / ".env")  # no-op if .env is absent

    path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    # Resolve + create output directories.
    resolved: dict[str, Path] = {}
    for key, rel in config.get("paths", {}).items():
        abs_path = (ROOT / rel).resolve()
        abs_path.mkdir(parents=True, exist_ok=True)
        resolved[key] = abs_path
    config["paths"] = resolved

    return config


def get_env(name: str, default: str | None = None) -> str | None:
    """Read an environment variable (after ``.env`` has been loaded)."""
    return os.environ.get(name, default)
