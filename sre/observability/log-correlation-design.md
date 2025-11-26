# Log Correlation Design
Each request generates:
- trace_id
- span_id
- correlation_id
This flows through Express middleware → FluentBit → Splunk/Datadog.
