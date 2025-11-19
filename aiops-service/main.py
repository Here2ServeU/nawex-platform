from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AIOps Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background: #f8f9fa;
            }
            .container {
                max-width: 800px;
                margin: 50px auto;
                background: #ffffff;
                padding: 25px;
                border-radius: 10px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }
            h1 {
                margin-bottom: 10px;
                color: #1e3a8a;
            }
            h2 {
                margin-top: 30px;
                color: #2563eb;
            }
            label {
                display: block;
                margin-bottom: 6px;
                font-weight: bold;
            }
            input {
                width: 100%;
                padding: 10px;
                margin-bottom: 15px;
                border-radius: 6px;
                border: 1px solid #d1d5db;
            }
            button {
                background: #2563eb;
                color: #fff;
                padding: 12px 20px;
                border: none;
                cursor: pointer;
                border-radius: 6px;
                font-size: 16px;
            }
            button:hover {
                background: #1d4ed8;
            }
            .result-box {
                background: #f3f4f6;
                padding: 15px;
                border-radius: 8px;
                margin-top: 10px;
                font-size: 15px;
                white-space: pre-wrap;
                line-height: 1.6;
            }
        </style>
    </head>

    <body>
        <div class="container">
            <h1>AIOps Dashboard</h1>
            <p>Predict risk, detect anomalies, and estimate monthly cloud cost.</p>

            <h2>Incident Risk Prediction</h2>
            <label>CPU Usage (%)</label>
            <input id="cpu" type="number" value="50">

            <label>Memory Usage (%)</label>
            <input id="memory" type="number" value="40">

            <label>Latency (ms) — optional</label>
            <input id="latency" type="number" placeholder="e.g. 120">

            <button onclick="predict()">Run Prediction</button>
            <div id="predict-output" class="result-box">Waiting...</div>

            <h2>FinOps Cost Estimator</h2>
            <label>CPU (millicores)</label>
            <input id="cpu_m" type="number" value="300">

            <label>Memory (MB)</label>
            <input id="mem_m" type="number" value="512">

            <button onclick="finops()">Estimate Cost</button>
            <div id="finops-output" class="result-box">Waiting...</div>
        </div>

        <script>
            async function predict() {
                const cpu = parseFloat(document.getElementById("cpu").value);
                const memory = parseFloat(document.getElementById("memory").value);

                // Convert empty latency field → null
                let latency_raw = document.getElementById("latency").value;
                const latency = latency_raw === "" ? null : parseFloat(latency_raw);

                const res = await fetch("/predict", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        cpu: cpu,
                        memory: memory,
                        latency_ms: latency
                    })
                });

                const data = await res.json();

                document.getElementById("predict-output").innerText = 
                    "Risk Score: " + data.risk_score +
                    "\\nSeverity: " + data.severity +
                    "\\nMessage: " + data.message;
            }

            async function finops() {
                const cpu_m = parseFloat(document.getElementById("cpu_m").value);
                const mem_m = parseFloat(document.getElementById("mem_m").value);

                const res = await fetch("/finops", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        cpu_millicores: cpu_m,
                        memory_mb: mem_m
                    })
                });

                const data = await res.json();

                document.getElementById("finops-output").innerText = 
                    "Estimated Monthly Cost: $" + data.estimated_monthly_cost +
                    "\\nRecommendation: " + data.recommendation;
            }
        </script>

    </body>
    </html>
    """
