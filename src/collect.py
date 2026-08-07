"""Data collection for Canuck4Frame.

Why not a CBC / Radio-Canada "news API"? Those outlets do not expose a public
keyword-search REST API. The reproducible, no-key alternative used here is the
**GDELT DOC 2.0 API** (https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/),
which continuously indexes worldwide online news — including cbc.ca,
ici.radio-canada.ca, ledevoir.com and tvanouvelles.ca — and lets us query by
keyword, domain and date range for free.

Pipeline:
    1. `discover_articles()` queries GDELT for the keyword, one outlet-domain at
       a time, and returns article *metadata* (title, url, date, domain, lang).
    2. `fetch_body()` downloads each article page and extracts the main text
       with BeautifulSoup (polite delay + retries via tenacity).
    3. `collect()` ties them together and writes newline-delimited JSON so a run
       interrupted halfway keeps whatever it already fetched.

GDELT's DOC index effectively begins in 2017; earlier years may return little.
That limitation is documented in the README.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Iterable, Iterator

import requests
from bs4 import BeautifulSoup
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tqdm import tqdm

from .config import get_env

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
# GDELT enforces a hard limit of ~1 request every 5 seconds; exceeding it
# returns HTTP 429 with a plain-text body. Stay comfortably above that.
GDELT_MIN_INTERVAL = 6.0


# --------------------------------------------------------------------------- #
# 1. Discovery (GDELT)                                                        #
# --------------------------------------------------------------------------- #
def _gdelt_query(keyword: str, domain: str) -> str:
    """Build a GDELT query string: keyword restricted to one outlet domain."""
    # Quote multi-word keywords; GDELT uses `domainis:` for exact-domain match.
    kw = f'"{keyword}"' if " " in keyword else keyword
    return f"{kw} domainis:{domain}"


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    # Wait at least one full rate-limit window (6s) before retrying a 429.
    wait=wait_exponential(multiplier=1, min=GDELT_MIN_INTERVAL, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _gdelt_request(params: dict) -> dict:
    resp = requests.get(GDELT_DOC_URL, params=params, timeout=30)
    # GDELT signals rate-limiting with 429 (and sometimes a 200 + plain-text
    # error page). Treat both as retryable RequestExceptions so tenacity backs
    # off instead of us crashing or parsing junk.
    if resp.status_code == 429:
        raise requests.RequestException("GDELT rate limit (429); backing off")
    resp.raise_for_status()
    if "application/json" not in resp.headers.get("Content-Type", ""):
        raise requests.RequestException(f"Non-JSON response from GDELT: {resp.text[:200]}")
    return resp.json()


def discover_articles(
    keyword: str,
    outlets: list[dict],
    start_date: str,
    end_date: str,
    max_records: int = 250,
) -> list[dict]:
    """Return metadata for every matching article across the given outlets.

    Dates are ``YYYY-MM-DD`` strings; GDELT wants ``YYYYMMDDHHMMSS``.
    """
    start = start_date.replace("-", "") + "000000"
    end = end_date.replace("-", "") + "235959"

    records: list[dict] = []
    for i, outlet in enumerate(outlets):
        # Respect GDELT's 1-request-per-5s limit between outlet queries.
        if i > 0:
            time.sleep(GDELT_MIN_INTERVAL)
        params = {
            "query": _gdelt_query(keyword, outlet["domain"]),
            "mode": "artlist",
            "format": "json",
            "maxrecords": max_records,
            "sort": "datedesc",
            "startdatetime": start,
            "enddatetime": end,
        }
        try:
            data = _gdelt_request(params)
        except requests.RequestException as exc:  # pragma: no cover - network
            print(f"  ! GDELT query failed for {outlet['domain']}: {exc}")
            continue

        for art in data.get("articles", []):
            records.append(
                {
                    "id": art.get("url", "").rstrip("/").rsplit("/", 1)[-1] or art.get("url"),
                    "title": art.get("title", "").strip(),
                    "url": art.get("url"),
                    "date": _normalize_seendate(art.get("seendate", "")),
                    "source": outlet["name"],
                    "domain": outlet["domain"],
                    # GDELT gives a language name (e.g. "English"); keep the hint.
                    "lang": _lang_hint(art.get("language", ""), outlet.get("lang")),
                    "body": None,  # filled in later by fetch_body()
                }
            )
        print(f"  {outlet['name']:<16} {len([r for r in records if r['source'] == outlet['name']]):>4} articles")
    return records


def _normalize_seendate(seendate: str) -> str:
    """GDELT seendate looks like '20230815T120000Z' -> '2023-08-15'."""
    if len(seendate) >= 8 and seendate[:8].isdigit():
        d = seendate[:8]
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
    return seendate


def _lang_hint(gdelt_lang: str, outlet_default: str | None) -> str:
    mapping = {"english": "en", "french": "fr"}
    return mapping.get(gdelt_lang.lower(), outlet_default or "unknown")


# --------------------------------------------------------------------------- #
# 2. Body fetching                                                            #
# --------------------------------------------------------------------------- #
def _user_agent() -> str:
    return get_env("SCRAPER_USER_AGENT") or "Canuck4Frame research bot"


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    stop=stop_after_attempt(3),
    reraise=False,  # a dead article shouldn't kill the whole run
)
def _download(url: str, timeout: int) -> str:
    resp = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_body(url: str, timeout: int = 20) -> str | None:
    """Download an article page and extract readable body text.

    Uses a generic heuristic (concatenate <p> tags inside <article>/<main>,
    falling back to all <p> tags) so it works across outlets without a
    per-site parser. Returns ``None`` on failure.
    """
    try:
        html = _download(url, timeout)
    except (requests.RequestException, RetryError):
        return None
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()

    container = soup.find("article") or soup.find("main") or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    text = "\n".join(p for p in paragraphs if len(p) > 40)
    return text or None


# --------------------------------------------------------------------------- #
# 3. Orchestration                                                            #
# --------------------------------------------------------------------------- #
def discover_from_mediacloud_csv(csv_path: str | Path, outlets: list[dict]) -> list[dict]:
    """Turn a MediaCloud CSV export into article metadata records.

    MediaCloud's Online News search exports columns:
    ``id, indexed_date, language, media_name, media_url, publish_date, title, url``
    — metadata + title + url, but *no* article body (fetched later by
    :func:`fetch_body`). We map those onto the same record shape produced by
    :func:`discover_articles` so the rest of the pipeline is unchanged.
    """
    import pandas as pd

    def _canon(dom: str) -> str:
        return str(dom).split("//")[-1].removeprefix("www.").strip("/")

    # Map a MediaCloud media_name back to the friendly outlet name from config.
    name_by_domain = {_canon(o["domain"]): o["name"] for o in outlets}

    def _match_name(media_name: str) -> str:
        m = _canon(media_name)
        for dom, name in name_by_domain.items():
            if dom == m or dom in m or m in dom:
                return name
        return media_name

    df = pd.read_csv(csv_path)
    records: list[dict] = []
    for _, row in df.iterrows():
        url = str(row.get("url", "")).strip()
        if not url:
            continue
        records.append(
            {
                "id": str(row.get("id"))
                or url.rstrip("/").rsplit("/", 1)[-1],
                "title": str(row.get("title", "")).strip(),
                "url": url,
                "date": _normalize_seendate(str(row.get("publish_date", "")).replace("-", "")),
                "source": _match_name(row.get("media_name", "")),
                "domain": _canon(row.get("media_name", "")),
                "lang": (str(row.get("language", "")).strip() or None),
                "body": None,  # filled in later by fetch_body()
            }
        )
    print(f"  Loaded {len(records)} articles from MediaCloud CSV: {csv_path}")
    return records


def _iter_existing_ids(path: Path) -> set[str]:
    """Read already-collected article urls so re-runs are incremental."""
    if not path.exists():
        return set()
    ids: set[str] = set()
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                ids.add(json.loads(line)["url"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids


def collect(config: dict, out_path: str | Path | None = None) -> Path:
    """Run discovery + body fetching, writing newline-delimited JSON.

    Returns the path to the raw JSONL file. Safe to re-run: articles whose URL
    is already present are skipped.
    """
    ds = config["data_source"]
    proj = config["project"]
    out_path = Path(out_path) if out_path else config["paths"]["raw"] / "articles_raw.jsonl"

    backend = ds.get("backend", "gdelt")
    if backend == "mediacloud":
        csv_path = ds.get("mediacloud_csv")
        if not csv_path:
            raise ValueError(
                "backend 'mediacloud' requires 'data_source.mediacloud_csv' "
                "(path to a MediaCloud CSV export) in config.yaml."
            )
        print(f"[1/2] Loading '{proj['keyword']}' articles from MediaCloud export …")
        metadata = discover_from_mediacloud_csv(csv_path, ds["outlets"])
    else:
        print(f"[1/2] Discovering '{proj['keyword']}' articles via GDELT …")
        metadata = discover_articles(
            keyword=proj["keyword"],
            outlets=ds["outlets"],
            start_date=proj["start_date"],
            end_date=proj["end_date"],
        )

    already = _iter_existing_ids(out_path)
    todo = [m for m in metadata if m["url"] not in already]
    print(f"[2/2] Fetching bodies for {len(todo)} new articles "
          f"({len(already)} already on disk) …")

    delay = ds.get("request_delay_seconds", 1.5)
    timeout = ds.get("timeout_seconds", 20)
    with open(out_path, "a", encoding="utf-8") as fh:
        for art in tqdm(todo, unit="article"):
            art["body"] = fetch_body(art["url"], timeout=timeout)
            fh.write(json.dumps(art, ensure_ascii=False) + "\n")
            fh.flush()
            time.sleep(delay)

    print(f"Done. Raw corpus at {out_path}")
    return out_path
