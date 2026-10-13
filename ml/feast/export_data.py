"""Write the offline feature table Feast reads (data/account_txn_features.parquet).

Uses the platform's own feature logic so Feast and golden.ai.features.store serve identical values:

    python ml/feast/export_data.py --transactions 5000
"""

import argparse
from pathlib import Path

from golden.ai.datasets.fintech_simulator import make_fraud_scenario_stream
from golden.ai.features.store import compute_account_features


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transactions", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    out = Path(__file__).parent / "data" / "account_txn_features.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    txns = make_fraud_scenario_stream(args.transactions, seed=args.seed)
    features = compute_account_features(txns)
    features.to_parquet(out, index=False)
    # Entity frame for training: every transaction with its label, as of its own timestamp.
    labels = txns[["account_id", "timestamp", "is_fraud"]].rename(columns={"timestamp": "event_timestamp"})
    labels.to_parquet(out.parent / "labels.parquet", index=False)
    print(f"wrote {len(features)} feature rows -> {out}")


if __name__ == "__main__":
    main()
