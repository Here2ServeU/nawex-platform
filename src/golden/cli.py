"""``golden`` command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal

from golden import __version__
from golden.logging import configure_logging


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


# ----------------------------------------------------------------------------- commands
def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from golden.services.registry import SERVICES

    target, port = SERVICES[args.service]
    configure_logging(args.service)
    port = args.port or int(os.getenv("PORT", port))
    uvicorn.run(target, host=args.host, port=port, log_config=None, proxy_headers=True)
    return 0


def cmd_roi(args: argparse.Namespace) -> int:
    from golden.ai.business_value import ROICalculator

    result = ROICalculator.quick_summary(args.vertical, tier=args.tier)
    _print(
        result
        if args.json
        else {
            k: result[k]
            for k in (
                "vertical",
                "tier",
                "monthly_cost_usd",
                "monthly_value_protected_usd",
                "roi_ratio",
                "payback_days",
                "annual_net_benefit_usd",
                "executive_summary",
            )
        }
    )
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    from golden.ai.training import train_and_save

    configure_logging("trainer")
    kinds: list[Literal["lstm", "tcn"]] = ["lstm", "tcn"] if args.model == "all" else [args.model]
    for kind in kinds:
        result = train_and_save(kind, output_dir=args.output_dir, epochs=args.epochs, device=args.device)
        _print(result.__dict__)
    return 0


def cmd_orchestrate(args: argparse.Namespace) -> int:
    from golden.ai.agents import Orchestrator

    configure_logging("orchestrator")
    results = Orchestrator().run(cycles=args.cycles, interval=args.interval)
    if args.cycles:
        _print(
            [{"analysis": r["analysis"]["status"], "execution": r["execution"]["status"]} for r in results]
        )
    return 0


def cmd_demo_client(args: argparse.Namespace) -> int:
    from golden.demo.client_demo import run_demo

    run_demo(args.vertical, args.client, Path(args.output), fast=args.fast)
    return 0


def cmd_demo_engine(args: argparse.Namespace) -> int:
    from golden.ai.demo_run import run_demo

    _print(run_demo(epochs=args.epochs, output_dir=Path(args.output_dir)))
    return 0


def cmd_security_status(_: argparse.Namespace) -> int:
    from golden.security import security_status

    _print(security_status())
    return 0


def cmd_security_manifest(args: argparse.Namespace) -> int:
    from golden.security import write_manifest

    print(write_manifest(args.model_dir))
    return 0


def cmd_gpu_doctor(_: argparse.Namespace) -> int:
    from golden.ai.accel import device_report

    _print(device_report())
    return 0


def cmd_gpu_analyze(args: argparse.Namespace) -> int:
    from golden.gpu import analyze_fleet, collect_local, make_gpu_fleet

    samples = collect_local() if args.local else make_gpu_fleet(scenario=args.scenario)
    report = analyze_fleet(samples, on_prem=args.on_prem).to_dict()
    if not args.verbose:
        report.pop("findings")
    _print(report)
    return 0


def _inventory(path: str | None):
    from golden.migration import load_inventory, sample_inventory

    return load_inventory(path) if path else sample_inventory()


def cmd_migrate_assess(args: argparse.Namespace) -> int:
    from golden.migration import assess_inventory

    result = assess_inventory(_inventory(args.inventory), bandwidth_gbps=args.bandwidth_gbps)
    _print(result if args.verbose else result["summary"])
    return 0


def cmd_migrate_plan(args: argparse.Namespace) -> int:
    from golden.migration import plan_waves

    plan = plan_waves(_inventory(args.inventory), max_vms_per_wave=args.max_vms, max_tb_per_wave=args.max_tb)
    _print(plan.to_dict())
    return 0


def cmd_migrate_manifests(args: argparse.Namespace) -> int:
    from golden.migration import MappingConfig, plan_waves, write_wave_manifests

    vms = _inventory(args.inventory)
    plan = plan_waves(vms, max_vms_per_wave=args.max_vms, max_tb_per_wave=args.max_tb)
    cfg = MappingConfig(
        source_provider=args.source_provider,
        target_namespace=args.target_namespace,
        default_storage_class=args.storage_class,
    )
    files = write_wave_manifests(args.output, plan.waves, vms, cfg)
    _print({"waves": [w.name for w in plan.waves], "files": [str(f) for f in files], "backlog": plan.backlog})
    return 0


def cmd_config_get(args: argparse.Namespace) -> int:
    from golden import platform_config

    value = platform_config.get(args.key, platform_config.load(args.file))
    print(
        " ".join(map(str, value))
        if isinstance(value, list)
        else str(value).lower()
        if isinstance(value, bool)
        else value
    )
    return 0


def cmd_config_show(args: argparse.Namespace) -> int:
    from golden import platform_config

    _print(platform_config.load(args.file))
    return 0


# ----------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    from golden.services.registry import SERVICES

    p = argparse.ArgumentParser(
        prog="golden", description="Golden Platform — enterprise modernization template"
    )
    p.add_argument("--version", action="version", version=f"golden {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("serve", help="run a platform service")
    s.add_argument("service", choices=sorted(SERVICES))
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int)
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("roi", help="compute engagement ROI for a vertical")
    s.add_argument("--vertical", choices=["healthcare", "fintech", "gpu", "migration"], default="healthcare")
    s.add_argument("--tier", choices=["starter", "professional", "enterprise"], default="professional")
    s.add_argument("--json", action="store_true", help="full JSON including breakdown/details")
    s.set_defaults(func=cmd_roi)

    s = sub.add_parser("train", help="train SLI forecasters (requires the [ml] extra; uses GPU if present)")
    s.add_argument("--model", choices=["lstm", "tcn", "all"], default="all")
    s.add_argument("--epochs", type=int, default=3)
    s.add_argument("--output-dir", default="models")
    s.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"], default=None)
    s.set_defaults(func=cmd_train)

    s = sub.add_parser("orchestrate", help="run the governed observe→analyze→plan→execute loop")
    s.add_argument("--cycles", type=int, default=None, help="number of cycles (default: run forever)")
    s.add_argument("--interval", type=float, default=None)
    s.set_defaults(func=cmd_orchestrate)

    demo = sub.add_parser("demo", help="demos").add_subparsers(dest="demo", required=True)
    s = demo.add_parser("client", help="narrated executive demo + HTML report")
    s.add_argument("--vertical", choices=["hospital", "bank", "gpu", "migration", "all"], default="hospital")
    s.add_argument("--client", default="Demo Client")
    s.add_argument("--output", default="demo_output")
    s.add_argument("--fast", action="store_true", help="no animation delays")
    s.set_defaults(func=cmd_demo_client)
    s = demo.add_parser("engine", help="end-to-end AI engine demo (train → infer → explain)")
    s.add_argument("--epochs", type=int, default=1)
    s.add_argument("--output-dir", default=".artifacts/demo")
    s.set_defaults(func=cmd_demo_engine)

    cfg = sub.add_parser("config", help="read platform.yaml").add_subparsers(dest="config", required=True)
    s = cfg.add_parser("get", help="print one value, e.g. cloud.provider")
    s.add_argument("key")
    s.add_argument("--file", default=None)
    s.set_defaults(func=cmd_config_get)
    s = cfg.add_parser("show", help="print the merged, validated configuration")
    s.add_argument("--file", default=None)
    s.set_defaults(func=cmd_config_show)

    sec = sub.add_parser("security", help="AI-safety controls").add_subparsers(dest="security", required=True)
    sec.add_parser("status", help="autonomy mode, kill switch, caps, audit chain").set_defaults(
        func=cmd_security_status
    )
    s = sec.add_parser("manifest", help="(re)write the SHA-256 model manifest")
    s.add_argument("--model-dir", default="models")
    s.set_defaults(func=cmd_security_manifest)

    gpu = sub.add_parser("gpu", help="GPU domain").add_subparsers(dest="gpu", required=True)
    gpu.add_parser("doctor", help="report available accelerators").set_defaults(func=cmd_gpu_doctor)
    s = gpu.add_parser("analyze", help="analyze a GPU fleet (simulated or local nvidia-smi)")
    s.add_argument("--scenario", choices=["typical", "hot", "efficient"], default="typical")
    s.add_argument("--local", action="store_true")
    s.add_argument("--on-prem", action="store_true")
    s.add_argument("--verbose", action="store_true")
    s.set_defaults(func=cmd_gpu_analyze)

    mig = sub.add_parser("migrate", help="VMware → OpenShift migration").add_subparsers(
        dest="migrate", required=True
    )
    for name, func, helptext in (
        ("assess", cmd_migrate_assess, "assess migration readiness"),
        ("plan", cmd_migrate_plan, "plan migration waves"),
        ("manifests", cmd_migrate_manifests, "generate MTV manifests per wave"),
    ):
        s = mig.add_parser(name, help=helptext)
        s.add_argument("--inventory", help="RVTools vInfo CSV, RVTools export dir, or JSON (default: sample)")
        s.add_argument("--verbose", action="store_true")
        s.add_argument("--bandwidth-gbps", type=float, default=10.0)
        s.add_argument("--max-vms", type=int, default=50)
        s.add_argument("--max-tb", type=float, default=20.0)
        s.add_argument("--output", default="deploy/openshift/virtualization/waves")
        s.add_argument("--source-provider", default="vsphere-prod")
        s.add_argument("--target-namespace", default="migrated-vms")
        s.add_argument("--storage-class", default="ocs-storagecluster-ceph-rbd-virtualization")
        s.set_defaults(func=func)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
