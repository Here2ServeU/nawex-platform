# inference

Runtime inference and risk aggregation helpers.

## Contents

- `runtime_inference.py`: Runs all sequence predictors and computes aggregate risk.

## Example

```python
from inference.runtime_inference import run_all_predictors, aggregate_risk

sequence = [120, 121, 125, 133, 147, 163, 181]
scores = run_all_predictors(sequence, model_dir="models")
risk = aggregate_risk(scores)
print(scores, risk)
```

## Integration

Use this module inside the `AnalyzerAgent` or API routes when producing
a consolidated risk signal for planner/executor stages.
