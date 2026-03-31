# datasets

This module contains synthetic and local dataset utilities for rapid demo runs.

## Contents

- `sample_data.py`: Generates reliability telemetry and fintech transaction samples.

## Typical Usage

```python
from datasets.sample_data import make_sli_dataset, make_transactions_dataset

sli_df = make_sli_dataset(n_rows=1000)
txn_df = make_transactions_dataset(n_rows=3000, mode="mixed")
```

## Notes

- Data is synthetic and safe for interview demonstrations.
- The generated schema is aligned to the `pipelines/` and `detection` utilities.
