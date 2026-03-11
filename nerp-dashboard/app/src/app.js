/**
 * WEB APP WORKLOAD - BUSINESS LOGIC LAYER
 * Version: v7.0.0 (AI-Ready)
 * -----------------------------------------------------------------------------
 * This file contains the standard Express application logic.
 * It is now fully instrumented to serve as a target for the Express AI Platform.
 */
const express = require('express');
const cors = require('cors');
const helmet = require('helmet'); // Security headers (SOC2 compliance)
const os = require('os');

const app = express();

// --- 1. OBSERVABILITY STATE ---
// These variables track the live health of the application
let metrics = {
    requestCount: 0,
    errorCount: 0,
    totalLatencyMs: 0,
    cpuStressActive: false,
    latencyInjectionMs: 0
};

// --- 2. MIDDLEWARE ---
app.use(helmet());
app.use(cors());
app.use(express.json());

// Telemetry Middleware: Tracks Latency & Errors for every request
app.use((req, res, next) => {
    const start = Date.now();
    metrics.requestCount++;

    // Hook into response finish to calculate duration
    res.on('finish', () => {
        const duration = Date.now() - start;
        metrics.totalLatencyMs += duration;
        
        if (res.statusCode >= 500) {
            metrics.errorCount++;
        }
    });

    // Simulate Network Latency (if injected by Chaos Engine)
    if (metrics.latencyInjectionMs > 0) {
        setTimeout(next, metrics.latencyInjectionMs);
    } else {
        next();
    }
});

// --- 3. BUSINESS ROUTES ---

app.get('/', (req, res) => {
    res.json({ 
        service: 'Web App Workload', 
        version: 'v7.1.0', 
        status: metrics.errorCount > 5 ? 'Degraded' : 'Operational',
        ai_governance: 'Enabled'
    });
});

app.get('/api/v7/users', (req, res) => {
    // Simulate DB call
    res.json([
        { id: 1, name: "Alice", role: "Admin" }, 
        { id: 2, name: "Bob", role: "User" } 
    ]);
});

// --- 4. TELEMETRY ENDPOINT (The "Eyes" for ObserverAgent) ---
// Your Python Observer can poll this endpoint to get real data
app.get('/metrics', (req, res) => {
    const uptime = process.uptime();
    const avgLatency = metrics.requestCount > 0 ? (metrics.totalLatencyMs / metrics.requestCount) : 0;
    const errorRate = metrics.requestCount > 0 ? (metrics.errorCount / metrics.requestCount) : 0;
    
    // Memory Usage (MB)
    const memUsage = process.memoryUsage();
    const heapUsedMB = Math.round(memUsage.heapUsed / 1024 / 1024);

    res.json({
        timestamp: new Date().toISOString(),
        service_id: "web-app-v7",
        metrics: {
            latency_ms: Math.round(avgLatency),        // Targets Rule-001 (Scale Up)
            error_rate: parseFloat(errorRate.toFixed(2)), // Targets Rule-002 (Restart)
            cpu_usage_percent: metrics.cpuStressActive ? 95.5 : 12.0, // Targets Rule-003 (Optimize)
            memory_usage_mb: heapUsedMB
        },
        chaos_state: {
            latency_injection_active: metrics.latencyInjectionMs > 0,
            cpu_stress_active: metrics.cpuStressActive,
            leaked_arrays: leakArray.length
        }
    });
});

// --- 5. CHAOS & REMEDIATION HOOKS (Triggers for AI) ---

let leakArray = [];

// Trigger Rule-001: High Latency
app.post('/chaos/latency', (req, res) => {
    const delay = req.body.delay || 500;
    metrics.latencyInjectionMs = delay;
    console.warn(`[CHAOS] Latency Injection Active: ${delay}ms per request`);
    res.json({ status: 'Latency Injected', delay_ms: delay });
});

// Trigger Rule-002: Error Spike
app.post('/chaos/error-spike', (req, res) => {
    // We artificially inflate the error count to trick the AI
    metrics.errorCount += 50; 
    console.warn(`[CHAOS] Artificial Error Spike Injected`);
    res.json({ status: 'Error Count Inflated', errors: metrics.errorCount });
});

// Trigger Rule-003: CPU Stress
app.post('/chaos/cpu', (req, res) => {
    metrics.cpuStressActive = true;
    console.warn(`[CHAOS] CPU Stress Flag Set`);
    // Note: We don't actually burn CPU here to keep the demo responsive, 
    // we just report high usage in /metrics
    res.json({ status: 'CPU Stress Reported' });
});

// Trigger Rule-004: Memory Leak
app.get('/chaos/stress-test', (req, res) => {
    const intensity = req.query.intensity || 1; 
    for (let i = 0; i < intensity; i++) {
        leakArray.push(new Array(1e6).fill('Web-App-Chaos-Data'));
    }
    console.warn(`[CHAOS] Memory Leak Active. Size: ${leakArray.length} MB`);
    res.json({ status: 'Stressing Memory', leaks: leakArray.length });
});

// --- REMEDIATION ACTIONS (The "Hands") ---

app.post('/ops/heal', (req, res) => {
    // 1. Reset Memory
    leakArray = [];
    global.gc && global.gc();
    
    // 2. Reset Metrics
    metrics.latencyInjectionMs = 0;
    metrics.cpuStressActive = false;
    metrics.errorCount = 0;
    metrics.requestCount = 0;
    metrics.totalLatencyMs = 0;

    console.log('[OPS] Self-Healing Signal Received. All systems normalized.');
    res.json({ status: 'Healed', message: 'Memory cleared, Latency reset, CPU normal.' });
});

module.exports = app;
