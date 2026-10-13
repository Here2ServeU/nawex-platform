#!/usr/bin/env python3
"""Parse every tracked YAML/JSON file (Helm templates excluded: the infra workflow renders them)."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import yaml

files = subprocess.run(["git", "ls-files", "*.yml", "*.yaml", "*.json"], capture_output=True, text=True, check=True).stdout.split()
bad = []
for f in files:
    if "/templates/" in f:
        continue
    try:
        text = pathlib.Path(f).read_text(encoding="utf-8")
        if f.endswith((".yml", ".yaml")):
            list(yaml.safe_load_all(text))
        else:
            json.loads(text)
    except Exception as exc:  # noqa: BLE001 - report every broken file, not just the first
        bad.append(f"{f}: {exc}")
print("\n".join(bad) or f"{len(files)} files OK")
sys.exit(1 if bad else 0)
