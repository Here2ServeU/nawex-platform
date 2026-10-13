"""LLM clients and the production LLM gateway.

Clients implement one method, ``complete(prompt, *, system, model, max_tokens) -> LLMResponse``:

* :class:`SimulatedLLM` — offline and deterministic (hash-seeded). The default everywhere a key is not
  configured, so tests, demos and CI never spend money.
* :class:`AnthropicLLM` — Claude through the official ``anthropic`` SDK (``pip install .[llm]``), with the
  SDK's own retry on 408/409/429/5xx, server-side refusal fallback, and explicit effort.

:class:`LLMGateway` wraps any client with the production concerns the course material builds up one by
one: input guardrails → per-caller daily token budget → response cache → model routing → retries with
exponential backoff and a fallback model → output scanning → cost + metrics. Every call returns the
same envelope so callers never special-case failures.
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from golden.agentops.guardrails import Classifier, check_input, scan_output
from golden.agentops.metrics import LLM_CALLS, LLM_LATENCY
from golden.agentops.pricing import Usage, cost_usd

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
ROUTING_SMALL_MODEL = "claude-haiku-5-5"


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: Usage
    stop_reason: str = "end_turn"
    request_id: str = ""

    @property
    def cost_usd(self) -> float:
        return cost_usd(self.model, self.usage)


class LLMError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class LLMClient(Protocol):
    def complete(
        self, prompt: str, *, system: str = "", model: str = DEFAULT_MODEL, max_tokens: int = 1024
    ) -> LLMResponse: ...


# ----------------------------------------------------------------------------- clients
class SimulatedLLM:
    """Deterministic offline model. ``fail_first`` simulates transient 5xx/429 for retry tests."""

    model_name = "simulated"

    def __init__(self, *, fail_first: int = 0, answer: Callable[[str, str], str] | None = None) -> None:
        self._failures_left = fail_first
        self._answer = answer
        self.calls = 0

    def complete(
        self, prompt: str, *, system: str = "", model: str = DEFAULT_MODEL, max_tokens: int = 1024
    ) -> LLMResponse:
        self.calls += 1
        if self._failures_left > 0:
            self._failures_left -= 1
            raise LLMError("simulated overloaded (529)", retryable=True)
        seed = int(hashlib.sha256(f"{system}\x00{prompt}".encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        text = self._answer(prompt, system) if self._answer else f"[simulated] {prompt.strip()[:160]}"
        usage = Usage(
            input_tokens=max(1, (len(system) + len(prompt)) // 4),
            output_tokens=min(max_tokens, max(1, len(text) // 4 + rng.randint(5, 40))),
        )
        return LLMResponse(text=text, model="simulated", usage=usage, request_id=f"sim_{seed:08x}")


class AnthropicLLM:
    """Claude via the official SDK. Credentials resolve the SDK's usual way (ANTHROPIC_API_KEY, profile…)."""

    def __init__(self, *, effort: str = "medium", timeout: float = 60.0, max_retries: int = 2) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise RuntimeError("install the llm extra: pip install 'golden-platform[llm]'") from exc
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(timeout=timeout, max_retries=max_retries)
        self.effort = effort

    def complete(  # pragma: no cover - needs network and credentials
        self, prompt: str, *, system: str = "", model: str = DEFAULT_MODEL, max_tokens: int = 1024
    ) -> LLMResponse:
        anthropic = self._anthropic
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {"effort": self.effort},
        }
        if system:
            kwargs["system"] = system
        try:
            if model in {"claude-opus-5-5", "claude-sonnet-5-5"}:
                # Server-side refusal fallback: the API re-runs a declined request on a suitable model.
                msg = self._client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                )
            else:
                msg = self._client.messages.create(**kwargs)
        except anthropic.RateLimitError as exc:
            raise LLMError(f"rate limited: {exc}", retryable=True) from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(
                f"API error {exc.status_code}: {exc.message}", retryable=exc.status_code >= 500
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError(f"connection error: {exc}", retryable=True) from exc
        text = "".join(b.text for b in msg.content if b.type == "text")
        u = msg.usage
        usage = Usage(
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            cache_creation_input_tokens=u.cache_creation_input_tokens or 0,
            cache_read_input_tokens=u.cache_read_input_tokens or 0,
        )
        return LLMResponse(
            text=text,
            model=msg.model,
            usage=usage,
            stop_reason=msg.stop_reason or "",
            request_id=msg._request_id or "",
        )


def default_client() -> LLMClient:
    """Anthropic when ``GOLDEN_LLM_PROVIDER=anthropic`` (and the extra is installed), else simulated."""
    if os.getenv("GOLDEN_LLM_PROVIDER", "simulated").lower() == "anthropic":
        return AnthropicLLM(effort=os.getenv("GOLDEN_LLM_EFFORT", "medium"))
    return SimulatedLLM()


def leaks_system_prompt(output: str, system: str, window: int = 24) -> bool:
    """LLM07: does the output reproduce any ``window``-char span of the system prompt (or its tokens)?"""
    if not system or not output:
        return False
    norm_out = " ".join(output.split()).lower()
    norm_sys = " ".join(system.split()).lower()
    if len(norm_sys) < window:
        return norm_sys in norm_out
    step = max(1, window // 2)
    if any(norm_sys[i : i + window] in norm_out for i in range(0, len(norm_sys) - window + 1, step)):
        return True
    # distinctive identifiers (codes, keys) leaked on their own
    return any(tok in norm_out for tok in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)+", norm_sys) if len(tok) >= 8)


# ----------------------------------------------------------------------------- gateway
@dataclass
class GatewayResult:
    status: str  # success | blocked | budget_exceeded | cache_hit | error | refusal
    text: str = ""
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    cached: bool = False
    attempts: int = 0
    guard: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMGateway:
    """Production wrapper around an :class:`LLMClient`. Thread-safe; state is per-process."""

    def __init__(
        self,
        client: LLMClient | None = None,
        *,
        model: str = DEFAULT_MODEL,
        fallback_model: str | None = "claude-sonnet-5-5",
        small_model: str | None = None,
        route_below_chars: int = 400,
        daily_tokens_per_caller: int = 50_000,
        cache_size: int = 512,
        max_attempts: int = 3,
        backoff_base: float = 2.0,
        backoff_max: float = 30.0,
        classifier: Classifier | None = None,
        protect_system_prompt: bool = True,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client or default_client()
        self.model = model
        self.fallback_model = fallback_model
        self.small_model = small_model
        self.route_below_chars = route_below_chars
        self.daily_tokens = daily_tokens_per_caller
        self.cache: OrderedDict[str, GatewayResult] = OrderedDict()
        self.cache_size = cache_size
        self.max_attempts = max_attempts
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.classifier = classifier
        self.protect_system_prompt = protect_system_prompt
        self._sleep = sleep
        self._usage: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    # --- helpers --------------------------------------------------------------------------------
    def tokens_used(self, caller: str) -> int:
        return self._usage.get((caller, datetime.now(UTC).date().isoformat()), 0)

    def _charge(self, caller: str, tokens: int) -> None:
        key = (caller, datetime.now(UTC).date().isoformat())
        with self._lock:
            self._usage[key] = self._usage.get(key, 0) + tokens

    def route(self, prompt: str) -> str:
        """Short, simple prompts go to the small model when one is configured (cost routing)."""
        if self.small_model and len(prompt) < self.route_below_chars:
            return self.small_model
        return self.model

    def _cache_key(self, prompt: str, system: str, model: str, max_tokens: int) -> str:
        return hashlib.sha256(f"{model}\x00{max_tokens}\x00{system}\x00{prompt}".encode()).hexdigest()

    # --- main -----------------------------------------------------------------------------------
    def complete(
        self, prompt: str, *, caller: str = "anonymous", system: str = "", max_tokens: int = 512
    ) -> GatewayResult:
        guard = check_input(prompt, classifier=self.classifier)
        if not guard.allowed:
            LLM_CALLS.labels(model=self.model, status="blocked").inc()
            return GatewayResult(status="blocked", guard=guard.to_dict())
        if self.tokens_used(caller) >= self.daily_tokens:
            LLM_CALLS.labels(model=self.model, status="budget_exceeded").inc()
            return GatewayResult(
                status="budget_exceeded", text=f"daily token budget of {self.daily_tokens} reached"
            )

        model = self.route(prompt)
        key = self._cache_key(prompt, system, model, max_tokens)
        if (hit := self.cache.get(key)) is not None:
            self.cache.move_to_end(key)
            LLM_CALLS.labels(model=model, status="cache_hit").inc()
            return GatewayResult(**{**hit.to_dict(), "status": "cache_hit", "cached": True, "cost_usd": 0.0})

        attempts, response, last_error = 0, None, ""
        candidates = [model] + (
            [self.fallback_model] if self.fallback_model and self.fallback_model != model else []
        )
        for candidate in candidates:
            for attempt in range(self.max_attempts):
                attempts += 1
                started = time.perf_counter()
                try:
                    response = self.client.complete(
                        prompt, system=system, model=candidate, max_tokens=max_tokens
                    )
                    LLM_LATENCY.labels(model=candidate).observe(time.perf_counter() - started)
                    break
                except LLMError as exc:
                    last_error = str(exc)
                    LLM_CALLS.labels(model=candidate, status="error").inc()
                    if not exc.retryable:
                        break
                    if attempt + 1 < self.max_attempts:
                        delay = min(self.backoff_max, self.backoff_base * 2**attempt) * (
                            0.5 + random.random() / 2
                        )
                        self._sleep(delay)
            if response is not None:
                break
        if response is None:
            logger.warning("llm call failed", extra={"error": last_error, "attempts": attempts})
            return GatewayResult(status="error", text=last_error, model=model, attempts=attempts)

        self._charge(caller, response.usage.input_tokens + response.usage.output_tokens)
        out = scan_output(response.text)
        if self.protect_system_prompt and leaks_system_prompt(response.text, system):
            out.allowed = False
            out.categories.append("system_prompt_leak")
            out.owasp = sorted({*out.owasp, "LLM07"})
        status = "refusal" if response.stop_reason == "refusal" else ("success" if out.allowed else "blocked")
        LLM_CALLS.labels(model=response.model, status=status).inc()
        result = GatewayResult(
            status=status,
            text=out.text if out.allowed else "[response withheld: output guardrail]",
            model=response.model,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=round(response.cost_usd, 6),
            attempts=attempts,
            guard=out.to_dict() if out.categories else {},
            request_id=response.request_id,
        )
        if status == "success":
            self.cache[key] = result
            while len(self.cache) > self.cache_size:
                self.cache.popitem(last=False)
        return result
