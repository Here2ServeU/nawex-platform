const express = require("express");
const path = require("path");
const client = require('prom-client');

// Initialize App FIRST
const app = express();

// Initialize Prometheus
const register = new client.Registry();
register.setDefaultLabels({ app: 'aiops-showcase-app' });
client.collectDefaultMetrics({ register });

// Serve static files
app.use(express.static(path.join(__dirname, 'public')));

// Metrics Endpoint
app.get('/metrics', async (req, res) => {
  res.setHeader('Content-Type', register.contentType);
  res.send(await register.metrics());
});

// Start Server
app.listen(3000, () => {
  console.log('Server is running on port 3000');
});
