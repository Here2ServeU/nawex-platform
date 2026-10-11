"""Global kill switch for autonomous actions.

Engaged when ``GOLDEN_KILL_SWITCH=true`` or when the file named by ``GOLDEN_KILL_SWITCH_FILE`` exists
(handy on Kubernetes: mount a ConfigMap key, or ``touch`` the file in an emergency). When engaged the
platform keeps detecting and recommending, but executes nothing.
"""

from __future__ import annotations

from pathlib import Path

from golden.config import get_settings
from golden.security.metrics import KILL_SWITCH


def is_engaged() -> bool:
    settings = get_settings()
    engaged = settings.kill_switch or bool(
        settings.kill_switch_file and Path(settings.kill_switch_file).exists()
    )
    KILL_SWITCH.set(1 if engaged else 0)
    return engaged
