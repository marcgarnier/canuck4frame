# Canuck4Frame — Research Protocol

Media framing of **4chan** in major Canadian news media (2017–2026).

This document is the authoritative, reproducible description of *what* the study
does and *why*. The [`README.md`](README.md) covers installation and commands;
this file covers the research design. Every operational parameter referenced here
lives in [`config.yaml`](config.yaml).

---

## 1. Research questions & hypotheses

**RQ1 — Framing.** Which frames do Canadian outlets use when covering 4chan
(e.g. *meme/internet-culture*, *far-right/extremism*, *crime/violence*,
*platform/technology*, *politics/elections*)?

**RQ2 — Temporal shift.** Do the dominant frames change across 2017–2026 — for
example, a drift from a "meme factory" framing toward a "far-right engine"
framing after high-profile events?

**RQ3 — Language divergence.** Does framing differ between **Francophone** and
**Anglophone** outlets?

**Working hypotheses.**

- **H1.** Coverage volume is event-driven (spikes around mass-violence events and
  elections) rather than steady.
- **H2.** The share of extremism/violence frames rises over the window relative to
  the meme/internet-culture frame.
- **H3.** Frame distribution is **not** independent of outlet language
  (tested with χ²; effect size via Cramér's V).

These are directional expectations, not preregistered predictions; the modeling
stage is unsupervised and can surface frames not anticipated here.

---

## 2. Corpus definition

**Unit of analysis.** One published news article that mentions 4chan.

**Population.** Articles from ten major Canadian outlets (public broadcasters +
leading private titles), published **2017-01-01 onward**.

| Outlet | Domain | Lang | Type |
|---|---|---|---|
| CBC News | `cbc.ca` | en | Public |
| Radio-Canada | `ici.radio-canada.ca` | fr | Public |
| The Globe and Mail | `theglobeandmail.com` | en | Major |
| National Post | `nationalpost.com` | en | Major |
| CTV News | `ctvnews.ca` | en | Major |
| Global News | `globalnews.ca` | en | Major |
| Toronto Star | `thestar.com` | en | Major |
| La Presse | `lapresse.ca` | fr | Major |
| Le Devoir | `ledevoir.com` | fr | Major |
| TVA Nouvelles | `tvanouvelles.ca` | fr | Major |

**Inclusion rule.** The article's indexed text matches the query `4chan OR
4chan.org` and originates from one of the ten source domains.

**Language.** Detected per article at preprocessing time (not assumed from the
outlet); each article is assigned `en` or `fr` for the comparative analysis.

---

## 3. Data source & sampling procedure

**Source: Media Cloud** (<https://search.mediacloud.org/>), an open news-index
database with deep per-outlet full-text coverage. No API key is used; the search
is run through the web UI and exported to CSV.

> **Why Media Cloud and not GDELT.** GDELT DOC 2.0 was tested first and returned
> **zero** "4chan" articles for the target outlets (and only ~4 for all of
> Canada), in addition to rejecting pre-2017 start dates and rate-limiting hard.
> Media Cloud returns a usable corpus (~340 articles) for the same outlets.

**Export procedure (reproducible).**

1. Query at <https://search.mediacloud.org/>:
   - *Match any of these phrases:* `4chan`, `4chan.org`
   - *Sources:* the ten domains in §2
   - *Dates:* `2017-01-01` → export date
2. Export to **CSV** → save under `data/mediacloud/` (e.g.
   `mc_4chan_2017_2026.csv`).
3. Set `config.yaml → data_source.mediacloud_csv` to that path and
   `data_source.backend: mediacloud`.

**Export schema (metadata only):**
`id, indexed_date, language, media_name, media_url, publish_date, title, url`.
The body text is **not** exported and is fetched separately (§4).

**Provenance.** The CSV filename encodes the export date; re-running the study
means re-exporting and committing a new CSV. The exact file used is the ground
truth of the corpus for that run.

---

## 4. Collection (body retrieval)

Implemented in `src/collect.py`.

1. `discover_from_mediacloud_csv()` parses the CSV into per-article records and
   maps each `media_name` back to a friendly outlet name.
2. For each record, `fetch_body()` downloads the article page and extracts main
   text (concatenated `<p>` inside `<article>`/`<main>`, generic across sites),
   with:
   - polite delay between requests (`request_delay_seconds`, default 1.5 s),
   - retries with exponential backoff (`tenacity`),
   - **graceful failure** — a page that 429s / paywalls / 404s is stored with an
     empty body rather than aborting the run.
3. Records are written incrementally to `data/raw/articles_raw.jsonl` (one JSON
   object per line), so an interrupted run keeps everything already fetched. Re-runs
   are idempotent: URLs already on disk are skipped.

**Record fields:** `id, title, url, date, source, domain, lang, body`.

---

## 5. Preprocessing

Implemented in `src/preprocess.py`.

- **Clean** — strip boilerplate/whitespace from each body.
- **Drop stubs** — remove articles whose cleaned body is shorter than
  `preprocess.min_chars` (default 200) — this is where failed/paywalled fetches
  fall out.
- **Deduplicate** — remove duplicate articles.
- **Language detection** — `langdetect` assigns `en`/`fr` per article.
- **Split** — write the combined corpus plus `en` and `fr` sub-corpora to
  `data/processed/`.

Report at this stage: articles kept vs dropped (with reason), and the EN/FR split.

---

## 6. Topic modeling

Implemented in `src/modeling.py`; parameters under `modeling:` in `config.yaml`.

- **Strategy** — `unified`: a single multilingual model over FR+EN (an optional
  `split` mode fits separate FR and EN models).
- **Embeddings** — `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- **Dimensionality reduction** — UMAP (`n_neighbors`, `n_components`, `min_dist`,
  cosine metric).
- **Clustering** — HDBSCAN (`min_cluster_size`, `min_samples`); topic `-1` is the
  outlier bucket.
- **Topic representation** — c-TF-IDF with combined EN+FR stopwords removed, and
  **protected terms** (`4chan`, `meme`, `memes`, `8chan`, `anon`, `imageboard`)
  never dropped, so framing-discriminative words survive.
- **Reproducibility** — fixed `random_state` (42).

Outputs: `data/results/topic_summary.csv` and a saved `bertopic_model/`.

**Small-corpus tuning.** With only a few hundred documents, expect many outliers.
If topic `-1` dominates, lower `umap.n_components → 2`, `hdbscan.min_cluster_size
→ 3`, `min_topic_size → 3`, and/or set `nr_topics: auto`.

---

## 7. Frame annotation (human coding)

BERTopic yields *topics* (word clusters), not *frames* (interpretive categories).
The mapping from topic → frame is a manual coding step:

1. For each topic, pull the **10 most representative articles**
   (`representative_docs()`).
2. Read them and assign a single **frame label** to the topic.
3. Record the mapping in `data/results/frames_annotation.csv`
   (`topic_id → frame_label`).

**Provisional codebook** (refine against the data; one frame per topic):

| Frame | Short definition |
|---|---|
| `meme_internet_culture` | 4chan as a source of memes / online subculture / humour |
| `far_right_extremism` | 4chan as a hub for far-right, hateful, or radicalizing content |
| `violence_crime` | 4chan tied to mass violence, threats, manifestos, policing |
| `platform_tech` | 4chan as a platform/technology story (moderation, outages, ownership) |
| `politics_elections` | 4chan in the context of elections, disinformation, campaigns |
| `other` | none of the above / mixed |

Inter-annotator agreement (e.g. a second coder on a subsample + Cohen's κ) is
recommended but out of scope for a single-coder run; note this as a limitation.

---

## 8. Analysis

Implemented in `src/visualization.py` and `src/stats.py`.

- **Volume over time** — article counts per year/outlet (`temporal_counts.csv`).
- **Frames over time** — frame share per year, stacked-area chart
  (`frames_over_time.png`, `temporal_analysis.csv`).
- **Interactive topics-over-time** — `topics_over_time.html`.
- **FR vs EN comparison** — frame share by language
  (`comparative_fr_en.png`, `comparative_fr_en.csv`).
- **Statistical test** — χ² test of independence between **frame** and
  **language** (`chi_square_fr_en`), reporting χ², p-value, and **Cramér's V**
  (effect size), written to `chi2_contingency.csv` and `chi2_fr_en_result.csv`.

**Decision rule for H3.** Reject independence at α = 0.05; interpret magnitude via
Cramér's V (small ≈ 0.1, medium ≈ 0.3, large ≈ 0.5). Report the effect size even
when the test is non-significant, given the modest sample.

---

## 9. Reproducibility

- **Single source of truth.** All parameters in `config.yaml`.
- **Deterministic modeling.** Fixed `random_state`.
- **Pinned environment.** `requirements.txt` / Docker image.
- **Committed corpus provenance.** The Media Cloud CSV export is committed under
  `data/mediacloud/`; generated data (`data/raw|processed|results`) is git-ignored
  and regenerable from that CSV via `python scripts/run_pipeline.py --collect`.
- **One-command run.** `run_pipeline.py` reproduces collection → preprocessing →
  modeling → analysis (frame annotation is the one manual step between modeling
  and the framed analysis).

---

## 10. Ethics & scope

The study analyzes **media discourse about 4chan**, not 4chan content or users. No
personal data is collected; only published news articles (public URLs and text)
are processed. Body fetching respects each outlet's terms of use and `robots.txt`,
with a conservative request delay. Article text is used for research analysis, not
redistribution.

---

## 11. Limitations

- **Coverage bias.** Media Cloud indexing depth varies by outlet; the niche
  keyword yields uneven per-outlet counts, so cross-outlet comparisons are
  descriptive, not representative.
- **Body-fetch attrition.** Paywalled/failed pages are dropped, which can skew
  which outlets survive into modeling (notably paywalled titles).
- **Small n.** A few hundred articles limits topic granularity and statistical
  power; results are exploratory.
- **Interpretive labels.** Single-coder frame assignment lacks reliability
  statistics.
- **Translation-free multilingual modeling.** A shared multilingual embedding
  space is convenient but may under-separate FR/EN nuances; the optional `split`
  strategy is the robustness check.
