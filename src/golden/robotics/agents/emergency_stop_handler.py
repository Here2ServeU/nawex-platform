"""Category 0 emergency stop (IEC 60204-1) — latches until a supervisor resets it."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class EmergencyStopHandler:
    def __init__(self) -> None:
        self.estop_active = False
        self.events: list[dict[str, Any]] = []

    def trigger_estop(self, source: str = "UNKNOWN", reason: str = "CRITICAL_SAFETY_FAULT") -> bool:
        """Engage the E-stop. Returns ``True`` if this call engaged it (idempotent afterwards)."""
        if self.estop_active:
            return False
        self.estop_active = True
        event = {
            "source": source,
            "reason": reason,
            "timestamp": time.time(),
            "actuator_power": "DISCONNECTED",
            "console_alert": "EMERGENCY STOP ENGAGED - CLEAR SURGICAL FIELD",
        }
        self.events.append(event)
        logger.critical("emergency stop engaged", extra=event)
        return True

    def reset(self, supervisor_key: str) -> bool:
        """Manual reset only — automatic restart after a Category 0 stop is never allowed."""
        if not supervisor_key:
            raise PermissionError("supervisor key required to reset the emergency stop")
        was_active, self.estop_active = self.estop_active, False
        return was_active
