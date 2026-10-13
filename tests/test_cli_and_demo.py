from __future__ import annotations

import json

import pytest

from golden.cli import build_parser, main


def test_help_lists_every_command():
    help_text = build_parser().format_help()
    for cmd in (
        "serve",
        "roi",
        "train",
        "orchestrate",
        "demo",
        "security",
        "gpu",
        "migrate",
        "iam",
        "agent",
        "llm",
        "rag",
        "model",
    ):
        assert cmd in help_text


@pytest.mark.parametrize("vertical", ["healthcare", "fintech", "gpu", "migration"])
def test_roi_command(vertical, capsys):
    assert main(["roi", "--vertical", vertical]) == 0
    assert json.loads(capsys.readouterr().out)["vertical"] == vertical


def test_security_status(capsys):
    main(["security", "status"])
    status = json.loads(capsys.readouterr().out)
    assert status["autonomy_mode"] == "dry_run"


def test_gpu_commands(capsys):
    main(["gpu", "analyze", "--scenario", "hot"])
    assert json.loads(capsys.readouterr().out)["hot_gpus"] > 0
    main(["gpu", "doctor"])
    assert "device" in json.loads(capsys.readouterr().out)


def test_migrate_commands(tmp_path, capsys):
    main(["migrate", "assess"])
    assert json.loads(capsys.readouterr().out)["blocked"] >= 2
    main(["migrate", "manifests", "--output", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert out["waves"] and all((tmp_path / w / "plan.yaml").exists() for w in out["waves"])


def test_orchestrate_cycles(capsys):
    main(["orchestrate", "--cycles", "2", "--interval", "0"])
    assert len(json.loads(capsys.readouterr().out)) == 2


@pytest.mark.parametrize("vertical", ["hospital", "bank", "gpu", "migration"])
def test_client_demo_writes_report(vertical, tmp_path, capsys):
    main(
        [
            "demo",
            "client",
            "--vertical",
            vertical,
            "--client",
            "Acme <Corp>",
            "--fast",
            "--output",
            str(tmp_path),
        ]
    )
    reports = list(tmp_path.glob(f"report_{vertical}_*.html"))
    assert len(reports) == 1
    html = reports[0].read_text()
    assert "Acme &lt;Corp&gt;" in html  # autoescaped
    assert "NAWEX" not in html and "{{" not in html


def test_platform_config(tmp_path, capsys):
    cfg = tmp_path / "platform.yaml"
    cfg.write_text("cloud:\n  provider: gcp\ndomains: [gpu]\n")
    (tmp_path / "platform.local.yaml").write_text("cloud:\n  region: europe-west4\n")
    main(["config", "get", "cloud.provider", "--file", str(cfg)])
    main(["config", "get", "cloud.region", "--file", str(cfg)])
    main(["config", "get", "domains", "--file", str(cfg)])
    assert capsys.readouterr().out.split() == ["gcp", "europe-west4", "gpu"]
    cfg.write_text("cloud:\n  provider: oracle\n")
    with pytest.raises(ValueError):
        main(["config", "show", "--file", str(cfg)])


def test_repo_platform_yaml_is_valid():
    from pathlib import Path

    from golden import platform_config

    config = platform_config.load(Path(__file__).parents[1] / "platform.yaml")
    assert config["cloud"]["provider"] in platform_config.CLOUDS
