/**
 * WEB APP WORKLOAD - ENTRY POINT
 * Version: v7.0.0 (AI-Ready)
 * -----------------------------------------------------------------------------
 * This file bootstraps the Express application and starts the HTTP server.
 * It separates server configuration (port, listeners) from app logic.
 */

const app = require('./app');
const http = require('http');

// Configuration
const PORT = process.env.PORT || 8080;
const SERVICE_NAME = "Web App Workload";

// Create HTTP Server
const server = http.createServer(app);

// Start Listener
server.listen(PORT, () => {
    console.log(`===========================================================`);
    console.log(`${SERVICE_NAME} v7.0.0 is running!`);
    console.log(`Listening on PORT: ${PORT}`);
    console.log(`AI Observability: http://localhost:${PORT}/metrics`);
    console.log(`Chaos Injection:  Enabled`);
    console.log(`===========================================================`);
});

// Graceful Shutdown Logic (Critical for Kubernetes/SRE)
// Ensures the app finishes current requests before dying when K8s scales it down.
process.on('SIGTERM', () => {
    console.info('SIGTERM signal received. Closing HTTP server...');
    server.close(() => {
        console.log('HTTP server closed.');
        process.exit(0);
    });
});

process.on('SIGINT', () => {
    console.info('SIGINT signal received. Closing HTTP server...');
    server.close(() => {
        console.log('HTTP server closed.');
        process.exit(0);
    });
});
