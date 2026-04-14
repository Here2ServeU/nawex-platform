# explainability

Model explanation helpers for incident tickets and postmortems.

## Contents

- `model_report.py`: Ranks and formats top feature contributors.

## Example

```python
from explainability.model_report import build_text_report

contrib = {
    "latency_ms": 0.81,
    "error_rate_percent": 0.44,
    "cpu_usage_percent": 0.22,
}

print(build_text_report(contrib, top_k=3))
```

## Output

Produces short plain-text summaries suitable for alerts, chat notifications,
and planner reasoning fields.
