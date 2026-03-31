"""One-command end-to-end demo for the NERP AI engine.

Usage:
    source .venv/bin/activate
    python demo_run.py --epochs 1 --output-dir .artifacts/demo
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
from pathlib import Path
import sys


def _bootstrap_package() -> None:
    """Expose this folder as importable package `nerp_ai_engine`."""
    package_name = "nerp_ai_engine"
    if package_name in sys.modules:
        return

    root = Path(__file__).resolve().parent
    init_file = root / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        package_name,
        init_file,
        submodule_search_locations=[str(root)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to bootstrap nerp_ai_engine package")

    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    spec.loader.exec_module(module)


_bootstrap_package()

make_sli_dataset = importlib.import_module("nerp_ai_engine.datasets").make_sli_dataset
regression_metrics = importlib.import_module("nerp_ai_engine.evaluation").regression_metrics
build_text_report = importlib.import_module("nerp_ai_engine.explainability").build_text_report
inference_mod = importlib.import_module("nerp_ai_engine.inference")
run_all_predictors = inference_mod.run_all_predictors
aggregate_risk = inference_mod.aggregate_risk


def _build_demo_sequence() -> list[float]:
    df = make_sli_dataset(n_rows=60, freq="5min")
    return [float(v) for v in df["latency_ms"].tail(24).tolist()]


def _build_demo_truth(sequence: list[float], predicted_risk: float) -> tuple[list[float], list[float]]:
    baseline = sequence[-1]
    truth = [baseline + offset for offset in (8.0, 10.0, 12.0)]
    forecast = [baseline + 12.0 * predicted_risk for _ in range(3)]
    return truth, forecast


def run_demo(epochs: int, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    lstm_path = "not_generated"
    tcn_path = "not_generated"
    training_mode = "fallback"
    training_error = ""
    try:
        train_and_save = importlib.import_module("nerp_ai_engine.training").train_and_save
        lstm_path = train_and_save("lstm", output_dir=output_dir, epochs=epochs)
        tcn_path = train_and_save("tcn", output_dir=output_dir, epochs=epochs)
        training_mode = "trained"
    except ModuleNotFoundError as exc:
        training_error = str(exc)

    sequence = _build_demo_sequence()
    scores = run_all_predictors(sequence, model_dir=output_dir)
    blended_risk = aggregate_risk(scores)

    y_true, y_pred = _build_demo_truth(sequence, blended_risk)
    quality = regression_metrics(y_true, y_pred)

    contributions = {
        "latency_recent_trend": scores.get("tcn_score", 0.0),
        "latency_level_shift": scores.get("lstm_score", 0.0),
        "error_budget_pressure": max(0.0, blended_risk - 0.15),
    }
    report = build_text_report(contributions, top_k=3)

    result = {
        "artifacts": {
            "lstm_model": str(lstm_path),
            "tcn_model": str(tcn_path),
        },
        "training_mode": training_mode,
        "training_error": training_error,
        "risk_scores": scores,
        "aggregate_risk": blended_risk,
        "evaluation": quality,
        "explainability": report,
    }

    output_file = output_dir / "demo_result.json"
    output_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run end-to-end NERP AI engine demo")
    parser.add_argument("--epochs", type=int, default=1, help="Training epochs per model")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/demo"),
        help="Directory where demo models and report are stored",
    )
    args = parser.parse_args()

    result = run_demo(epochs=max(args.epochs, 1), output_dir=args.output_dir)

    print("\n=== NERP AI Engine Demo Complete ===")
    print(f"LSTM model: {result['artifacts']['lstm_model']}")
    print(f"TCN model: {result['artifacts']['tcn_model']}")
    print(f"Training mode: {result['training_mode']}")
    if result["training_error"]:
        print(f"Training fallback reason: {result['training_error']}")
    print(f"Risk scores: {result['risk_scores']}")
    print(f"Aggregate risk: {result['aggregate_risk']:.4f}")
    print(f"Evaluation (RMSE): {result['evaluation']['rmse']:.4f}")
    print(result["explainability"])


if __name__ == "__main__":
    main()
