"""Golden Platform — end-to-end enterprise modernization template.

Domains: healthcare, fintech, GPU/AI-infrastructure optimization and VMware → OpenShift migration,
sharing one AI engine, decision engine and AI-safety layer.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("golden-platform")
except PackageNotFoundError:  # pragma: no cover - running from a source checkout without install
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
