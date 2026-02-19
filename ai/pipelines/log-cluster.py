# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans

# --- Configuration (Should be loaded from agent_config.yaml) ---
LOG_FILE_PATH = 'data/service_logs.json'
N_CLUSTERS = 50
BATCH_SIZE = 500

def load_logs(file_path):
    """Loads and preprocesses log data."""
    try:
        df = pd.read_json(file_path, lines=True)
        # Assuming logs have a 'message' field
        df['message'] = df['message'].astype(str).str.lower()
        return df
    except Exception as e:
        print(f"Error loading logs: {e}")
        return pd.DataFrame({'message': []})

def cluster_logs(df):
    """Clusters log messages using TF-IDF and MiniBatchKMeans."""
    if df.empty or df['message'].empty:
        print("No log messages to process.")
        return

    print(f"Loaded {len(df)} log messages.")

    # 1. Feature Extraction (TF-IDF)
    vectorizer = TfidfVectorizer(stop_words='english', min_df=5)
    X = vectorizer.fit_transform(df['message'])

    # 2. Clustering (MiniBatchKMeans for efficiency with large data)
    kmeans = MiniBatchKMeans(n_clusters=N_CLUSTERS, random_state=42, batch_size=BATCH_SIZE, n_init='auto')
    df['log_cluster'] = kmeans.fit_predict(X)

    print(f"Clustering complete. Found {N_CLUSTERS} clusters.")
    # Store results (e.g., save centroids for anomaly detection later)
    # pd.to_pickle(kmeans, 'models/log_cluster_model.pkl')
    # df[['timestamp', 'message', 'log_cluster']].to_csv('data/clustered_logs.csv')

if __name__ == "__main__":
    log_data = load_logs(LOG_FILE_PATH)
    cluster_logs(log_data)
