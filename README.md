# Canuck4Frame

**Media framing of 4chan in major Canadian news media (2017–2026).**

A reproducible computational-social-science pipeline that identifies, quantifies,
and tracks the **media frames** that ten major Canadian outlets — public
broadcasters and leading private titles — use when they cover the platform
**4chan**, via unsupervised, transformer-based topic modeling (BERTopic).

> **Research question.** How do Canadian outlets frame 4chan, and do those frames
> shift over time (e.g. from *"meme factory"* to *"far-right engine"*)? Is there a
> difference between Francophone and Anglophone coverage?

See [`PROTOCOL.md`](PROTOCOL.md) for the full research protocol (sampling, coding
scheme, statistics, reproducibility).

---

## Data source: Media Cloud (CSV export)

Canuck4Frame builds its corpus from **[Media Cloud](https://search.mediacloud.org/)**,
an open research database that indexes the full text of millions of news stories
worldwide, with deep, reliable per-outlet coverage.

> **Why not GDELT?** The pipeline originally targeted GDELT DOC 2.0, but GDELT's
> index contains essentially **no** "4chan" articles for the target Canadian
> outlets (0 for cbc.ca, radio-canada.ca, ledevoir.com, tvanouvelles.ca). Media
> Cloud returns a real corpus (≈340 articles across the ten outlets).

### How the corpus is obtained

Media Cloud is queried **manually through its web UI** (no API key required), then
exported to CSV:

1. Go to <https://search.mediacloud.org/> and build a search:
   - **Search phrases:** `4chan` OR `4chan.org`
   - **Sources:** the ten outlets below (add each by domain)
   - **Dates:** `2017-01-01 → present`
2. Export the results to **CSV** and drop the file in `data/mediacloud/`.
3. Point `config.yaml → data_source.mediacloud_csv` at that file.

The export contains metadata only — `id, indexed_date, language, media_name,
media_url, publish_date, title, url` — **not** the article body. Bodies are
downloaded from each URL by the pipeline's polite scraper (`fetch_body`), with
retries and incremental saves; pages that fail (paywalls, dead links, rate-limits)
are stored with an empty body and dropped during preprocessing.

### The ten outlets

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

---

## Project structure

```
canuck4frame/
├── config.yaml               # single source of truth for all parameters
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── .env.example
├── src/
│   ├── config.py             # load config.yaml + .env
│   ├── collect.py            # Media Cloud CSV import + body fetching
│   ├── preprocess.py         # clean, dedupe, language-split
│   ├── modeling.py           # BERTopic (unified or split FR/EN)
│   ├── stats.py              # chi-square FR vs EN frame independence
│   └── visualization.py      # temporal + comparative charts
├── notebooks/
│   ├── 01_data_collection.ipynb
│   ├── 02_preprocessing.ipynb
│   ├── 03_bertopic_modeling.ipynb
│   └── 04_analysis_visualization.ipynb
├── scripts/
│   └── run_pipeline.py       # end-to-end CLI
├── data/
│   ├── mediacloud/           # Media Cloud CSV export(s)
│   └── raw/ processed/ results/   # generated (git-ignored)
└── tests/
```

---

## Installation

```bash
git clone https://github.com/marcgarnier/canuck4frame.git
cd canuck4frame

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

The first BERTopic run downloads a sentence-transformer model (a few hundred MB)
and NLTK stopwords.

---

## Quick start

Make sure a Media Cloud CSV export sits in `data/mediacloud/` and is referenced in
`config.yaml` (see **Data source** above).

**Run the whole pipeline (import corpus + fetch bodies, then analyze):**

```bash
python scripts/run_pipeline.py --collect
```

**Re-run analysis only, on an already-collected corpus:**

```bash
python scripts/run_pipeline.py --skip-collect
```

**Or step through interactively** — run the notebooks in order (`01` → `04`).

**With Docker:**

```bash
docker compose run pipeline          # full pipeline
docker compose up jupyter            # Jupyter Lab at http://localhost:8888
```

Artifacts land in `data/results/`: `topic_summary.csv`, `frames_over_time.png`,
`temporal_analysis.csv`, `comparative_fr_en.png`, `chi2_fr_en_result.csv`,
`topics_over_time.html`, and a saved `bertopic_model/`.

---

## Methodology (summary)

1. **Collect** — import the Media Cloud CSV export, then download each article body
   from its URL with retries (`tenacity`) and incremental JSONL saves.
2. **Preprocess** — strip boilerplate, drop stubs (`< min_chars`) and duplicates,
   detect language per article (`langdetect`), split into EN/FR sub-corpora.
3. **Model** — BERTopic over multilingual sentence embeddings
   (`paraphrase-multilingual-MiniLM-L12-v2`) with UMAP + HDBSCAN. Stopwords
   (EN+FR) removed in the c-TF-IDF step, with discriminative terms
   (`4chan`, `meme`, …) protected.
4. **Annotate** — read the 10 most representative articles per topic and assign a
   human frame label (`frames_annotation.csv`).
5. **Analyze** — frame share per year (stacked area), `topics_over_time`, and a
   French-vs-English comparison with a χ² test of independence.

All knobs live in [`config.yaml`](config.yaml). The full procedure — sampling
frame, coding scheme, and statistics — is in [`PROTOCOL.md`](PROTOCOL.md).

---

## Tuning for small corpora

The corpus is small (a few hundred articles). If BERTopic returns mostly outliers
(topic `-1`):

- lower `modeling.umap.n_components` → `2`
- lower `modeling.hdbscan.min_cluster_size` → `3`
- lower `modeling.min_topic_size` → `3`
- optionally set `modeling.nr_topics: auto` to merge similar topics

---

## Ethics & scope

This project analyzes **media discourse about 4chan**, not content produced by
4chan users. No personal data is collected; only published news articles (public
URLs and their text) are processed. Respect each outlet's terms of use and
`robots.txt` when fetching bodies, and keep the request delay in `config.yaml`
conservative.

---

## Limitations & future work

- **Media Cloud coverage** shapes the corpus: indexing depth varies by outlet and
  the "4chan" keyword is niche, so counts per outlet are uneven.
- The generic body scraper can miss or truncate paywalled articles; those rows are
  dropped, which can bias which outlets survive to the modeling stage.
- Frame labels are interpretive; inter-annotator agreement would strengthen them.
- Future: supervised validation of frames, more outlets, sentiment/stance layering,
  and effect sizes (Cramér's V) reported alongside χ².

---

## Testing

```bash
pip install pytest
pytest tests/
```

(`tests/` covers the lightweight, non-ML pieces: text cleaning, language
detection, and the FR/EN chi-square statistics.)

---

## License

[MIT](LICENSE).

*Suggested venues for write-up: Canadian Journal of Communication, New Media &
Society, Journal of Information Technology & Politics.*
