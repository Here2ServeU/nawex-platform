// ===========================================================================
// Golden Platform — reference workload
// Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
// ===========================================================================
// apps/workload/src/server.js — process bootstrap (port binding, signals).
// ===========================================================================
'use strict';

const http = require('node:http');
const { createApp, optionsFromEnv, SERVICE_NAME } = require('./app');

const PORT = Number.parseInt(process.env.PORT || '8080', 10);
const HOST = process.env.HOST || '0.0.0.0';
const SHUTDOWN_TIMEOUT_MS = Number.parseInt(process.env.SHUTDOWN_TIMEOUT_MS || '10000', 10);

const app = createApp(optionsFromEnv());
const server = http.createServer(app);

server.listen(PORT, HOST, () => {
  console.log(JSON.stringify({ level: 'info', msg: 'listening', service: SERVICE_NAME, host: HOST, port: PORT, chaos_enabled: app.locals.config.chaosEnabled }));
});

let shuttingDown = false;
function shutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(JSON.stringify({ level: 'info', msg: 'shutdown', signal }));
  app.locals.shutdown();
  const force = setTimeout(() => {
    server.closeAllConnections();
    process.exit(1);
  }, SHUTDOWN_TIMEOUT_MS);
  force.unref();
  // Stop accepting new connections; finish in-flight requests.
  server.close(() => process.exit(0));
  server.closeIdleConnections();
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
