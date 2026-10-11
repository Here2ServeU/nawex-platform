"""Log pattern clustering (TF-IDF + MiniBatchKMeans) for incident triage. Requires the ``[ml]`` extra."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_logs(path: str | Path) -> pd.DataFrame:
    """Load JSON-lines logs with a ``message`` field."""
    df = pd.read_json(path, lines=True)
    df["message"] = df["message"].astype(str).str.lower()
    return df


def cluster_logs(
    df: pd.DataFrame, n_clusters: int = 50, batch_size: int = 500, min_df: int = 2
) -> pd.DataFrame:
    """Return ``df`` with a ``log_cluster`` column. ``n_clusters`` is capped at the number of messages."""
    if df.empty:
        return df.assign(log_cluster=pd.Series(dtype=int))
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectors = TfidfVectorizer(stop_words="english", min_df=min(min_df, len(df))).fit_transform(df["message"])
    k = max(1, min(n_clusters, len(df)))
    model = MiniBatchKMeans(n_clusters=k, random_state=42, batch_size=batch_size, n_init="auto")
    return df.assign(log_cluster=model.fit_predict(vectors))
