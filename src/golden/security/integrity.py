"""Model artifact integrity: SHA-256 manifests and safe checkpoint loading.

Training writes ``manifest.json`` next to its checkpoints. At load time every checkpoint is verified
against the manifest (``GOLDEN_MODEL_MANIFEST`` or ``<model_dir>/manifest.json``) before torch ever
deserializes it, and torch is always asked for ``weights_only=True`` so a tampered file cannot run
arbitrary code via pickle.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class IntegrityError(RuntimeError):
    pass


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(directory: str | Path, pattern: str = "*.pt") -> Path:
    directory = Path(directory)
    files = {p.name: sha256_file(p) for p in sorted(directory.glob(pattern))}
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps({"algorithm": "sha256", "files": files}, indent=2), encoding="utf-8")
    return manifest


def load_manifest(path: str | Path) -> dict[str, str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("algorithm", "sha256") != "sha256":
        raise IntegrityError(f"unsupported manifest algorithm in {path}")
    return dict(data.get("files", {}))


def verify_artifact(
    path: str | Path, manifest_path: str | Path | None = None, *, required: bool = False
) -> bool:
    """Verify ``path`` against its manifest.

    Returns ``True`` when verified, ``False`` when no manifest exists and ``required`` is false.
    Raises :class:`IntegrityError` on a hash mismatch, a missing entry, or a missing manifest when
    ``required`` is true.
    """
    path = Path(path)
    manifest_file = Path(manifest_path) if manifest_path else path.parent / "manifest.json"
    if not manifest_file.exists():
        if required:
            raise IntegrityError(f"model manifest not found: {manifest_file}")
        return False
    expected = load_manifest(manifest_file).get(path.name)
    if expected is None:
        raise IntegrityError(f"{path.name} is not listed in {manifest_file}")
    actual = sha256_file(path)
    if actual != expected:
        raise IntegrityError(
            f"checksum mismatch for {path.name}: expected {expected[:12]}…, got {actual[:12]}…"
        )
    return True


def safe_torch_load(
    path: str | Path, manifest_path: str | Path | None = None, *, required: bool = False
) -> Any:
    """Integrity-check then load a checkpoint with ``weights_only=True`` on CPU."""
    import torch

    verify_artifact(path, manifest_path, required=required)
    return torch.load(str(path), map_location="cpu", weights_only=True)
