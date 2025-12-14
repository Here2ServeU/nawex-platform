import time
import requests
import numpy as np
import tensorflow as tf
from prometheus_api_client import PrometheusConnect

# CONFIGURATION
PROMETHEUS_URL = "http://prometheus:9090"
SLACK_WEBHOOK_URL = "YOUR_SLACK_WEBHOOK_HERE" # <--- REPLACE THIS
METRIC_NAME = "http_request_duration_seconds_sum"
POLL_INTERVAL = 10
WINDOW_SIZE = 10  # How many data points the LSTM looks back

print("AIOps Engine Starting...")
prom = PrometheusConnect(url=PROMETHEUS_URL, disable_ssl=True)

# SIMPLIFIED LSTM MODEL BUILDER
def build_model():
    model = tf.keras.Sequential([
        tf.keras.layers.LSTM(50, activation='relu', input_shape=(WINDOW_SIZE, 1)),
        tf.keras.layers.Dense(1)
    ])
    model.compile(optimizer='adam', loss='mse')
    return model

model = build_model()
data_buffer = []

def send_slack_alert(predicted, actual):
    payload = {
        "text": f"*AIOps Anomaly Detected*\n*Metric:* {METRIC_NAME}\n*Predicted:* {predicted:.4f}\n*Actual:* {actual:.4f}\n*Deviation:* High"
    }
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload)
        print("✅ Slack Alert Sent!")
    except Exception as e:
        print(f"❌ Failed to send Slack alert: {e}")

print("Waiting for data stream to build baseline...")

while True:
    # 1. FETCH DATA
    # Fetching the last 1 minute of data
    metric_data = prom.get_current_metric_value(metric_name=METRIC_NAME)
    
    if not metric_data:
        print("Waiting for traffic...")
        time.sleep(POLL_INTERVAL)
        continue

    # Extract value (simplified for demo: taking the first series found)
    current_val = float(metric_data[0]['value'][1])
    print(f"Current Metric: {current_val}")

    data_buffer.append(current_val)

    # 2. RUN AI (Once we have enough data)
    if len(data_buffer) > WINDOW_SIZE:
        # Prepare input for LSTM
        input_seq = np.array(data_buffer[-WINDOW_SIZE:]).reshape((1, WINDOW_SIZE, 1))
        
        # Predict
        prediction = model.predict(input_seq, verbose=0)[0][0]
        
        # 3. DETECT ANOMALY (Simple Threshold Logic for Demo)
        # In real life, you'd use Standard Deviation here. 
        # For the demo, if actual is 2x the predicted, we alert.
        if current_val > (prediction * 2.0) and current_val > 0.1:
            print(f"ANOMALY! Pred: {prediction} | Act: {current_val}")
            send_slack_alert(prediction, current_val)
        
        # Online Training (The model learns from this new point)
        # This makes it 'adaptive' in real-time
        model.fit(input_seq, np.array([current_val]), epochs=1, verbose=0)
        
        # Maintain sliding window
        data_buffer.pop(0)

    time.sleep(POLL_INTERVAL)
