"""Recover missing article bodies from the Internet Archive (Wayback Machine).

Reads ``data/raw/articles_missing.csv`` (dead / blocked / body-less links),
looks up the closest Wayback snapshot near each article's publish date, fetches
the raw archived page, and extracts the body with trafilatura. Recovered
articles are appended to ``data/raw/articles_raw.jsonl`` (with
``retrieved_via: "wayback"`` for provenance); the still-missing rows are written
back to ``data/raw/articles_missing.csv``.

Run: python scripts/recover_wayback.py
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import requests
import trafilatura

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "articles_raw.jsonl"
MISSING = ROOT / "data" / "raw" / "articles_missing.csv"

AVAIL_API = "https://archive.org/wayback/available"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
DELAY = 5.0  # be polite to archive.org (its availability API rate-limits hard)


def _get(url: str, **kwargs) -> requests.Response | None:
    """GET with backoff on 429/5xx from archive.org (up to ~5 tries)."""
    wait = 10.0
    for attempt in range(5):
        try:
            r = requests.get(url, headers=HEADERS, timeout=45, **kwargs)
        except requests.RequestException:
            time.sleep(wait); wait *= 1.6; continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(wait); wait *= 1.6; continue
        return r
    return None


def closest_snapshot(url: str, ts: str) -> str | None:
    """Return the raw archived URL for the snapshot closest to ``ts`` (YYYYMMDD)."""
    r = _get(AVAIL_API, params={"url": url, "timestamp": ts})
    if r is None or not r.ok:
        return None
    try:
        snap = r.json().get("archived_snapshots", {}).get("closest")
    except ValueError:
        return None
    if not snap or not snap.get("available"):
        return None
    # Insert `id_` after the timestamp to get the raw page (no Wayback banner/JS).
    stamp = snap["timestamp"]
    return f"https://web.archive.org/web/{stamp}id_/{url}"


def fetch_archived_body(archived_url: str) -> str | None:
    r = _get(archived_url)
    if r is None or not r.ok:
        return None
    text = trafilatura.extract(r.text, include_comments=False, include_tables=False)
    return text if (text and len(text) >= 200) else None


def _already_have() -> set[str]:
    """URLs already present in the corpus (so re-runs skip them)."""
    if not RAW.exists():
        return set()
    have = set()
    for line in open(RAW, encoding="utf-8"):
        try:
            have.add(json.loads(line)["url"])
        except (json.JSONDecodeError, KeyError):
            continue
    return have


def main() -> None:
    with open(MISSING, newline="") as f:
        fieldnames = csv.DictReader(f).fieldnames
        f.seek(0)
        missing = list(csv.DictReader(f))

    have = _already_have()
    todo = [r for r in missing if r["url"] not in have]
    print(f"Wayback recovery: {len(todo)} to try ({len(missing) - len(todo)} already recovered).", flush=True)

    recovered_urls: set[str] = set()
    raw_fh = open(RAW, "a", encoding="utf-8")  # append + flush each hit (resumable)
    for i, row in enumerate(todo, 1):
        url = row["url"]
        ts = (row.get("date", "") or "").replace("-", "") or "20200101"
        archived = closest_snapshot(url, ts)
        body = fetch_archived_body(archived) if archived else None
        if body:
            rec = {
                "id": url.rstrip("/").rsplit("/", 1)[-1],
                "title": row.get("title", ""),
                "url": url,
                "date": row.get("date", ""),
                "source": row.get("source", ""),
                "domain": row.get("domain", ""),
                "lang": row.get("lang") or None,
                "body": body,
                "retrieved_via": "wayback",
            }
            raw_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            raw_fh.flush()
            recovered_urls.add(url)
            print(f"  [{i}/{len(todo)}] OK   {row['source']:<16} {len(body)}c  {url[:70]}", flush=True)
        else:
            print(f"  [{i}/{len(todo)}] miss {row['source']:<16}          {url[:70]}", flush=True)
        time.sleep(DELAY)
    raw_fh.close()

    # Rewrite the missing file: keep rows still absent from the corpus.
    have = _already_have()
    still = [r for r in missing if r["url"] not in have]
    with open(MISSING, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(still)

    print(f"\nDone. Recovered {len(recovered_urls)} this run; {len(still)} still missing.", flush=True)


if __name__ == "__main__":
    sys.exit(main())
