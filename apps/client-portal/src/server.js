// ===========================================================================
// Golden Platform
// Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
// ===========================================================================
// apps/client-portal/src/server.js — process bootstrap (port binding, signals).
// ===========================================================================
'use strict';

const { createPortal, portalOptionsFromEnv, SERVICE_NAME } = require('./app');

const PORT = Number.parseInt(process.env.PORT || '3001', 10);
const HOST = process.env.HOST || '0.0.0.0';
const SHUTDOWN_TIMEOUT_MS = Number.parseInt(process.env.SHUTDOWN_TIMEOUT_MS || '10000', 10);

const portal = createPortal(portalOptionsFromEnv());

portal.server.listen(PORT, HOST, () => {
  portal.start();
  console.log(JSON.stringify({ level: 'info', msg: 'listening', service: SERVICE_NAME, host: HOST, port: PORT }));
});

let shuttingDown = false;
function shutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(JSON.stringify({ level: 'info', msg: 'shutdown', signal }));
  const hardExit = setTimeout(() => process.exit(1), SHUTDOWN_TIMEOUT_MS + 2000);
  hardExit.unref();
  portal
    .close({ timeoutMs: SHUTDOWN_TIMEOUT_MS })
    .then(() => process.exit(0))
    .catch(() => process.exit(1));
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
