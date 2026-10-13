"""Service foundation shared by every Golden Platform microservice.

``create_app()`` returns a FastAPI app with the platform's non-negotiables already wired in:

* ``/health`` (liveness), ``/ready`` (readiness), ``/metrics`` (Prometheus text)
* API-key auth (``GOLDEN_API_KEYS``) and per-caller token-bucket rate limiting
* request body size cap, request IDs, security headers
* guardrail violations → HTTP 422 with a stable ``reason`` (and a metric)
* request count / latency metrics labelled by route template (bounded cardinality)
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from golden import __version__
from golden.config import get_settings
from golden.security.auth import match_api_key
from golden.security.guardrails import GuardrailViolation
from golden.security.metrics import AUTH_FAILURES, GUARDRAIL_REJECTIONS, RATE_LIMITED
from golden.security.ratelimit import RateLimiter

logger = logging.getLogger(__name__)

PUBLIC_PATHS = frozenset({"/health", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"})

HTTP_REQUESTS = Counter(
    "golden_http_requests_total", "HTTP requests.", ["service", "method", "path", "status"]
)
HTTP_LATENCY = Histogram(
    "golden_http_request_duration_seconds",
    "HTTP request latency.",
    ["service", "method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", "unmatched")


def create_app(service: str, description: str = "", ready_check: Callable[[], bool] | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=f"golden {service}", version=__version__, description=description)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    app.state.service = service
    app.state.limiter = limiter

    @app.middleware("http")
    async def platform_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        current = get_settings()
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        path = request.url.path

        response: Response
        length = request.headers.get("content-length")
        caller = (
            match_api_key(request.headers.get("x-api-key"), current.api_keys)
            if current.auth_enabled
            else None
        )
        if length and length.isdigit() and int(length) > current.max_body_bytes:
            response = JSONResponse({"detail": "request body too large"}, status_code=413)
        elif path not in PUBLIC_PATHS and current.auth_enabled and caller is None:
            AUTH_FAILURES.labels(service=service).inc()
            response = JSONResponse({"detail": "missing or invalid API key"}, status_code=401)
        else:
            # Bucket by key index when authenticated, otherwise by client address.
            bucket = (
                f"key-{caller}" if caller is not None else (request.client.host if request.client else "anon")
            )
            if path not in PUBLIC_PATHS and not limiter.allow(bucket):
                RATE_LIMITED.labels(service=service).inc()
                response = JSONResponse(
                    {"detail": "rate limit exceeded"}, status_code=429, headers={"Retry-After": "60"}
                )
            else:
                response = await call_next(request)

        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if not path.startswith(("/docs", "/redoc")):
            response.headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
            response.headers.setdefault("Cache-Control", "no-store")
        response.headers["X-Request-ID"] = request_id

        template = _route_template(request)
        HTTP_REQUESTS.labels(service, request.method, template, str(response.status_code)).inc()
        HTTP_LATENCY.labels(service, request.method, template).observe(time.perf_counter() - started)
        return response

    @app.exception_handler(GuardrailViolation)
    async def guardrail_handler(_: Request, exc: GuardrailViolation) -> JSONResponse:
        GUARDRAIL_REJECTIONS.labels(service=service, reason=exc.reason).inc()
        return JSONResponse({"detail": str(exc), "reason": exc.reason}, status_code=422)

    @app.get("/health", tags=["platform"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": service, "version": __version__}

    @app.get("/ready", tags=["platform"])
    def ready() -> Response:
        ok = ready_check() if ready_check else True
        return JSONResponse({"ready": ok, "service": service}, status_code=200 if ok else 503)

    @app.get("/metrics", tags=["platform"], include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


# ----------------------------------------------------------------------------- chaos engineering
MAX_CHAOS_LATENCY_MS = 10_000


class LatencyChaos(BaseModel):
    delay_ms: int = Field(500, ge=0, le=MAX_CHAOS_LATENCY_MS)


class ErrorChaos(BaseModel):
    error_rate: float = Field(0.1, ge=0.0, le=1.0)


@dataclass
class ChaosState:
    latency_ms: int = 0
    error_rate: float = 0.0

    async def apply(self) -> bool:
        """Sleep for injected latency; return ``True`` when this request should fail."""
        if self.latency_ms:
            await asyncio.sleep(self.latency_ms / 1000)
        return self.error_rate > 0 and random.random() < self.error_rate


def chaos_router(state: ChaosState) -> APIRouter:
    """Bounded fault injection for game days (disable with ``GOLDEN_CHAOS_ENABLED=false``)."""
    import os

    router = APIRouter(prefix="/ops", tags=["chaos"])

    def _enabled() -> None:
        if os.getenv("GOLDEN_CHAOS_ENABLED", "true").lower() in {"0", "false", "no"}:
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="chaos endpoints disabled")

    @router.post("/chaos/latency")
    def inject_latency(body: LatencyChaos) -> dict:
        _enabled()
        state.latency_ms = int(body.delay_ms)
        logger.warning("chaos latency injected", extra={"delay_ms": state.latency_ms})
        return {"chaos": "latency_injected", "delay_ms": state.latency_ms}

    @router.post("/chaos/error")
    def inject_errors(body: ErrorChaos) -> dict:
        _enabled()
        state.error_rate = float(body.error_rate)
        logger.warning("chaos errors injected", extra={"error_rate": state.error_rate})
        return {"chaos": "errors_injected", "error_rate": state.error_rate}

    @router.post("/reset")
    def reset() -> dict:
        state.latency_ms, state.error_rate = 0, 0.0
        return {"status": "reset", "latency_ms": 0, "error_rate": 0.0}

    return router


def run(app: FastAPI | str, port: int, host: str = "0.0.0.0") -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_config=None, proxy_headers=True)
