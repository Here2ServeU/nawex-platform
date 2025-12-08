# Express.js Reference Microservice

This directory contains the source code for the **Reference Workload** of the platform. It is a Node.js/Express application designed specifically to demonstrate **Observability-Driven Development**.

Unlike a standard "Hello World" app, this microservice is heavily instrumented to emit "Golden Signals" (Latency, Traffic, Errors, Saturation) and includes chaos endpoints to simulate production failures.

## Directory Structure

* **`src/`**: Application source code.
    * `app.js`: Main entry point initializing the Express server.
    * `tracing.js`: **OpenTelemetry SDK** configuration (must run before any other module).
    * `routes/`: API endpoints.
* **`Dockerfile`**: Multi-stage build definition for creating a lightweight, secure container image (Distroless or Alpine).
* **`package.json`**: Defines dependencies, including `prom-client` (metrics) and `@opentelemetry/sdk-node` (traces).

## Core Capabilities & SRE Value

### 1. Built-in Observability
* **Feature:** The app automatically exposes a `/metrics` endpoint for Prometheus scraping.
* **SRE Value:** **Zero-Touch Instrumentation.** New developers don't need to learn how to monitor their code; the base framework handles request duration buckets and error counters automatically.

### 2. Distributed Tracing (OpenTelemetry)
* **Feature:** Every incoming HTTP request is assigned a `trace-id`. If this service calls a database or another API, the context is propagated.
* **SRE Value:** **Full-Stack Visibility.** We can visualize the entire request journey in Jaeger/Splunk, identifying exactly which microservice is the bottleneck.

### 3. "Chaos" Endpoints
* **Feature:** The app includes specific routes to simulate bad behavior:
    * `GET /error`: Intentionally throws a 500 Internal Server Error.
    * `GET /slow`: Sleeps for 2 seconds before responding (simulating high latency).
    * `GET /leak`: Simulates a memory leak.
* **SRE Value:** **Resilience Testing.** These endpoints are used by the `sre/chaos` scripts to validate that our alerts fire correctly when things go wrong.

## Local Development

**Prerequisites:** Node.js v18+

```bash
# 1. Install dependencies
npm install

# 2. Start the app (with tracing enabled)
npm start
````

**Testing Endpoints:**

  * Health Check: `curl http://localhost:8080/health`
  * Metrics: `curl http://localhost:8080/metrics`
  * Simulate Error: `curl http://localhost:8080/error`

## Docker Usage

The `Dockerfile` is optimized for production (caching layers, non-root user).

```bash
# Build
docker build -t aiops-app .

# Run
docker run -p 8080:8080 aiops-app
```

### Talking Point
> I wrote this `app` to be the 'guinea pig' for my platform. It’s not just a web server; it’s a **telemetry generator**. I built in specific endpoints like `/slow` and `/error` so I could trigger failures on demand and verify that my AIOps engine detects them within seconds. This proves the feedback loop between the Application layer and the Infrastructure layer.
