# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
# Demonstration of log clustering using TF-IDF + KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

logs = [
    "timeout connecting to db",
    "db connection refused",
    "user login success",
    "cache miss for user id 22",
    "timeout fetching user profile"
]

vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(logs)

kmeans = KMeans(n_clusters=2)
kmeans.fit(X)

print("Cluster assignments:", kmeans.labels_)
