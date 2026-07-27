"""BERTopic modeling: inductively extract media frames from the corpus.

Two strategies, selected via ``modeling.strategy`` in config.yaml:

  * "unified" — one multilingual embedding model over the combined FR+EN corpus
    (default). Best when the corpus is small: pooling languages gives HDBSCAN
    more documents to find stable clusters.
  * "split"   — separate models per language, enabling a clean FR-vs-EN
    comparison at the cost of even smaller per-model corpora.

Stopword handling lives here (in the c-TF-IDF vectorizer) rather than in
preprocessing, and protected terms like "4chan"/"meme" are always kept.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Heavy ML imports are deferred to call-time so that lightweight steps
# (config, preprocessing) don't pay the import cost.


def _stopwords(protected: list[str]) -> list[str]:
    """Combined English + French stopword list, minus the protected terms."""
    from nltk.corpus import stopwords

    try:
        words = set(stopwords.words("english")) | set(stopwords.words("french"))
    except LookupError:  # corpus not downloaded yet
        import nltk

        nltk.download("stopwords", quiet=True)
        words = set(stopwords.words("english")) | set(stopwords.words("french"))

    return sorted(words - {t.lower() for t in protected})


def build_vectorizer(protected: list[str]):
    from sklearn.feature_extraction.text import CountVectorizer

    return CountVectorizer(
        stop_words=_stopwords(protected),
        ngram_range=(1, 2),
        min_df=2,
    )


def _embedding_model_name(mcfg: dict, lang: str | None) -> str:
    if mcfg["strategy"] == "unified" or lang is None:
        return mcfg["embedding_model_multilingual"]
    return mcfg["embedding_model_en"] if lang == "en" else mcfg["embedding_model_fr"]


def build_topic_model(config: dict, lang: str | None = None):
    """Construct a configured (unfitted) BERTopic model.

    ``lang`` selects the embedding model under the "split" strategy; pass None
    (the default) for the unified multilingual model.
    """
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from sentence_transformers import SentenceTransformer
    from umap import UMAP

    m = config["modeling"]
    embedding_model = SentenceTransformer(_embedding_model_name(m, lang))

    umap_model = UMAP(
        n_neighbors=m["umap"]["n_neighbors"],
        n_components=m["umap"]["n_components"],
        min_dist=m["umap"]["min_dist"],
        metric=m["umap"]["metric"],
        random_state=m["random_state"],
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=m["hdbscan"]["min_cluster_size"],
        min_samples=m["hdbscan"]["min_samples"],
        metric=m["hdbscan"]["metric"],
        prediction_data=True,
    )
    vectorizer_model = build_vectorizer(config["preprocess"]["protected_terms"])

    nr_topics = m.get("nr_topics")
    return BERTopic(
        embedding_model=embedding_model,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer_model,
        min_topic_size=m["min_topic_size"],
        nr_topics=nr_topics if nr_topics not in (None, "null") else None,
        calculate_probabilities=True,
        verbose=True,
    )


def fit_model(config: dict, df: pd.DataFrame, lang: str | None = None):
    """Fit BERTopic on ``df['text']`` and return (model, topics, probs)."""
    docs = df["text"].tolist()
    model = build_topic_model(config, lang=lang)
    topics, probs = model.fit_transform(docs)
    return model, topics, probs


def topic_summary(model) -> pd.DataFrame:
    """Tidy per-topic table: id, size, and top c-TF-IDF keywords."""
    info = model.get_topic_info()
    info["keywords"] = info["Topic"].apply(
        lambda t: ", ".join(w for w, _ in (model.get_topic(t) or [])[:10])
        if t != -1
        else ""
    )
    return info.rename(columns={"Topic": "topic_id", "Count": "count", "Name": "name"})


def representative_docs(model, df: pd.DataFrame, topics: list[int], top_n: int = 10) -> pd.DataFrame:
    """Return the ``top_n`` most representative articles per topic.

    Useful for the manual frame-annotation step (Step 4 of the plan).
    """
    doc_info = model.get_document_info(df["text"].tolist())
    doc_info = doc_info.reset_index(drop=True)
    joined = pd.concat(
        [df.reset_index(drop=True), doc_info[["Topic", "Probability", "Representative_document"]]],
        axis=1,
    )
    reps = (
        joined[joined["Representative_document"]]
        .sort_values(["Topic", "Probability"], ascending=[True, False])
        .groupby("Topic")
        .head(top_n)
    )
    return reps[["Topic", "Probability", "source", "date", "title", "url"]]


def save_model(model, path: str | Path) -> None:
    model.save(str(path), serialization="safetensors", save_ctfidf=True)
