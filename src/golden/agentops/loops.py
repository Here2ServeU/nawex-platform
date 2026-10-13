"""Loop detection: the cheapest money an agent ever saves.

A step is summarised as a signature ``"type:target"``. Three patterns, checked in order:

* **stuck**    — the last ``stuck_threshold`` signatures are identical (retrying the same call).
* **bouncing** — the last ``2·bounce_cycles`` signatures alternate between exactly two values (A,B,A,B…).
* **drifting** — ``drift_window`` steps without progress (no new target touched; exploring forever).

Progress is supplied by the caller (it knows what "new" means for its task).
"""

from __future__ import annotations

from collections import deque


class LoopDetector:
    def __init__(
        self, stuck_threshold: int = 3, bounce_cycles: int = 3, drift_window: int = 12, enabled: bool = True
    ) -> None:
        self.stuck_threshold = stuck_threshold
        self.bounce_cycles = bounce_cycles
        self.drift_window = drift_window
        self.enabled = enabled
        self.history: deque[str] = deque(maxlen=64)
        self.steps_since_progress = 0

    def observe(self, signature: str, *, progress: bool) -> str | None:
        self.history.append(signature)
        self.steps_since_progress = 0 if progress else self.steps_since_progress + 1
        if not self.enabled:
            return None
        h = list(self.history)
        if len(h) >= self.stuck_threshold and len(set(h[-self.stuck_threshold :])) == 1:
            return "stuck"
        window = h[-2 * self.bounce_cycles :]
        if (
            len(window) == 2 * self.bounce_cycles
            and len(set(window)) == 2
            and all(window[i] != window[i + 1] for i in range(len(window) - 1))
        ):
            return "bouncing"
        if self.steps_since_progress >= self.drift_window:
            return "drifting"
        return None
