# Canuck4Frame

**Media framing of 4chan in Canadian government-funded media (2015–2025).**

A fully reproducible computational-social-science pipeline that identifies,
quantifies, and tracks the **media frames** used by Canadian government-funded
and major outlets (CBC, Radio-Canada, Le Devoir, TVA Nouvelles) when they cover
the platform **4chan** — using unsupervised, transformer-based topic modeling
(BERTopic).

> **Research question.** How do Canadian outlets frame 4chan, and do those frames
> shift over time (e.g. from *"meme factory"* to *"far-right engine"*)? Is there
> a difference between Francophone and Anglophone coverage?

---

## ⚠️ A note on data sources (read this first)

To keep the project genuinely reproducible, Canuck4Frame instead collects articles through the
free, key-less **[GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)**,
which continuously indexes worldwide online news — including the four target
outlets — and supports keyword + domain + date filtering.

Two practical consequences:

- **Coverage starts ~2017.** GDELT's document index has limited depth before
  2017, so early years in the 2015–2025 window may return few or no articles.
- **Bodies are fetched from the live web.** GDELT returns metadata; article text
  is downloaded from each URL with a generic, polite scraper. Some pages fail
  (paywalls, dead links); those articles are dropped during preprocessing.

A **synthetic sample corpus** (`data/sample/`) is bundled so you can run the
entire pipeline offline in seconds — it is clearly *not* real journalism and is
only for smoke-testing the code.

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
│   ├── collect.py            # GDELT discovery + body fetching
│   ├── preprocess.py         # clean, dedupe, language-split
│   ├── modeling.py           # BERTopic (unified or split FR/EN)
│   └── visualization.py      # temporal + comparative charts
├── notebooks/
│   ├── 01_data_collection.ipynb
│   ├── 02_preprocessing.ipynb
│   ├── 03_bertopic_modeling.ipynb
│   └── 04_analysis_visualization.ipynb
├── scripts/
│   ├── run_pipeline.py       # end-to-end CLI
│   └── make_sample.py        # regenerate the synthetic sample
├── data/
│   ├── raw/ processed/ results/   # generated (git-ignored)
│   └── sample/               # committed synthetic corpus
└── tests/
```

---

## Installation

```bash
git clone https://github.com/<you>/canuck4frame.git
cd canuck4frame

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # optional — GDELT needs no key
```

The first BERTopic run downloads a sentence-transformer model (a few hundred MB)
and NLTK stopwords.

---

## Quick start

**Run the whole pipeline on the bundled sample (offline, ~1 min):**

```bash
python scripts/run_pipeline.py --sample
```

**Run it on the real corpus (collects from GDELT, then analyzes):**

```bash
python scripts/run_pipeline.py --collect
```

**Or step through interactively** — run the notebooks in order (`01` → `04`).

**With Docker:**

```bash
docker compose run pipeline          # sample pipeline
docker compose up jupyter            # Jupyter Lab at http://localhost:8888
```

Artifacts land in `data/results/`: `topic_summary.csv`, `frames_over_time.png`,
`temporal_analysis.csv`, `comparative_fr_en.png`, `topics_over_time.html`, and a
saved `bertopic_model/`.

---

## Methodology

1. **Collect** — GDELT DOC query `"4chan" domainis:<outlet>` per outlet + date
   range; article bodies fetched with retries (`tenacity`) and incremental saves.
2. **Preprocess** — strip boilerplate, drop stubs (`< min_chars`) and duplicates,
   detect language per article (`langdetect`), split into EN/FR sub-corpora.
3. **Model** — BERTopic over multilingual sentence embeddings
   (`paraphrase-multilingual-MiniLM-L12-v2`) with UMAP + HDBSCAN. Stopwords
   (EN+FR) removed in the c-TF-IDF step, with discriminative terms
   (`4chan`, `meme`, …) protected.
4. **Annotate** — read the 10 most representative articles per topic and assign a
   human frame label (`frames_annotation.csv`).
5. **Analyze** — frame share per year (stacked area), `topics_over_time`, and a
   French-vs-English comparison.

All knobs live in [`config.yaml`](config.yaml). For a small corpus, drop
`umap.n_components` to 2–3 and `hdbscan.min_cluster_size` to 3.

---

## Tuning for small corpora

The 4chan corpus is small (often 100–300 articles). If BERTopic returns mostly
outliers (topic `-1`):

- lower `modeling.umap.n_components` → `2`
- lower `modeling.hdbscan.min_cluster_size` → `3`
- lower `modeling.min_topic_size` → `3`
- optionally set `modeling.nr_topics: auto` to merge similar topics

---

## Ethics & scope

This project analyzes **media discourse about 4chan**, not content produced by
4chan users. No personal data is collected; only published news articles (public
URLs and their text) are processed. Respect each outlet's terms of use and
`robots.txt` when collecting, and keep the request delay in `config.yaml`
conservative.

---

## Limitations & future work

- GDELT coverage bias (indexing gaps, ~2017 start) shapes the corpus.
- The generic body scraper can miss or truncate paywalled articles.
- Frame labels are interpretive; inter-annotator agreement would strengthen them.
- Future: add supervised validation of frames, more outlets, χ² significance
  testing for FR/EN divergence, and sentiment/stance layering.

---

## Testing

```bash
pip install pytest
pytest tests/
```

(`tests/` covers the lightweight, non-ML pieces: cleaning, language detection,
GDELT query building.)

---

## License

[MIT](LICENSE).

*Suggested venues for write-up: Canadian Journal of Communication, New Media &
Society, Journal of Information Technology & Politics.*
