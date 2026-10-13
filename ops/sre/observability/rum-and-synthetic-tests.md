# Real User Monitoring (RUM) & Synthetic Testing Strategy

## 1. Overview
This document defines the frontend observability standards for the Express AIOps platform. We utilize a dual-approach strategy:
1. **RUM (Real User Monitoring):** Captures *actual* user experience, including JavaScript errors, network latency, and session replays.
2. **Synthetic Testing:** Simulates user journeys and API calls from global locations to proactively detect downtime before real users are impacted.

---

## 2. Real User Monitoring (RUM)

We use the Datadog RUM SDK to instrument the frontend React/Express application.

### Initialization
The RUM client must be initialized in the main entry point of the frontend application (e.g., `index.js` or `App.tsx`).

```javascript
import { datadogRum } from '@datadog/browser-rum';

datadogRum.init({
    applicationId: process.env.REACT_APP_DD_RUM_APP_ID,
    clientToken: process.env.REACT_APP_DD_CLIENT_TOKEN,
    site: 'datadoghq.com',
    service: 'nrp-frontend',
    env: process.env.NODE_ENV || 'production',
    version: process.env.REACT_APP_VERSION,
    sessionSampleRate: 100,
    sessionReplaySampleRate: 20, // Record 20% of sessions for replay
    trackUserInteractions: true,
    trackResources: true,
    trackLongTasks: true,
    defaultPrivacyLevel: 'mask-user-input',
});

datadogRum.startSessionReplayRecording();

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
