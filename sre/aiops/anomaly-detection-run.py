from ai.pipelines.detect_anomalies import detect_anomalies
from ai.pipelines.data_loader import load_sli_data

df = load_sli_data("latency")
anomalies = detect_anomalies(df)
print("Anomalies found:", anomalies.head())
