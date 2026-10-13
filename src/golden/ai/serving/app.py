"""HTTP front end for :class:`FraudModelServer` — the Open Inference Protocol REST endpoints.

Run with ``uvicorn golden.ai.serving.app:app`` (or ``golden serve model-server`` once the service is
registered in ``golden.services.registry``). Environment:

* ``GOLDEN_MODEL_REGISTRY`` — registry root (default ``models/registry``; mount a PVC/S3 sync here)
* ``GOLDEN_SERVING_MODEL``  — model name (default ``fraud-detector``)
* ``GOLDEN_SERVING_ALIAS``  — alias to serve (default ``champion``; ``challenger`` for a canary pod)

Endpoints: ``/v2/health/live``, ``/v2/health/ready``, ``/v2/models/{name}``,
``/v2/models/{name}/ready``, ``POST /v2/models/{name}/infer`` and ``POST /v2/models/{name}/reload``.
The platform's ``/health`` and ``/ready`` (from ``create_app``) are used for Kubernetes probes.
"""

from __future__ import annotations

import contextlib
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from golden.ai.lifecycle.registry import ModelRegistry
from golden.ai.serving.protocol import InferenceError
from golden.ai.serving.server import DEFAULT_MODEL, FraudModelServer
from golden.services.common import create_app

SERVICE = "model-server"


def build_server() -> FraudModelServer:
    server = FraudModelServer(
        ModelRegistry(os.getenv("GOLDEN_MODEL_REGISTRY", "models/registry")),
        os.getenv("GOLDEN_SERVING_MODEL", DEFAULT_MODEL),
        alias=os.getenv("GOLDEN_SERVING_ALIAS", "champion"),
    )
    # Not ready until a champion exists: /ready reports 503 until POST /v2/models/{name}/reload succeeds.
    with contextlib.suppress(KeyError, FileNotFoundError, ValueError):
        server.load()
    return server


def make_app(server: FraudModelServer | None = None) -> FastAPI:
    srv = server or build_server()
    app = create_app(SERVICE, "Open Inference Protocol (V2) model server.", ready_check=lambda: srv.ready)
    app.state.model_server = srv

    def _error(e: InferenceError) -> JSONResponse:
        return JSONResponse(e.to_dict(), status_code=e.status)

    def _check_name(name: str) -> None:
        if name != srv.name:
            raise InferenceError(f"model {name!r} not found", 404)

    @app.get("/v2/health/live")
    def live() -> dict[str, bool]:
        return {"live": True}

    @app.get("/v2/health/ready")
    def ready() -> JSONResponse:
        return JSONResponse({"ready": srv.ready}, status_code=200 if srv.ready else 503)

    @app.get("/v2/models/{name}")
    def metadata(name: str) -> Any:
        try:
            _check_name(name)
        except InferenceError as e:
            return _error(e)
        return srv.metadata().to_dict()

    @app.get("/v2/models/{name}/ready")
    def model_ready(name: str) -> JSONResponse:
        ok = name == srv.name and srv.ready
        return JSONResponse({"name": name, "ready": ok}, status_code=200 if ok else 503)

    @app.post("/v2/models/{name}/infer")
    async def infer(name: str, request: Request) -> JSONResponse:
        try:
            _check_name(name)
            try:
                body = await request.json()
            except ValueError:
                raise InferenceError("request body is not valid JSON") from None
            resp = srv.infer(body)
        except InferenceError as e:
            return _error(e)
        return JSONResponse(resp.to_dict(), headers=srv.response_headers(resp))

    @app.post("/v2/models/{name}/reload")
    def reload(name: str) -> Any:
        try:
            _check_name(name)
        except InferenceError as e:
            return _error(e)
        swapped = srv.reload()
        return {"name": srv.name, "version": srv.version, "swapped": swapped, "ready": srv.ready}

    return app


def __getattr__(attr: str) -> Any:
    # Lazily build the module-level ``app`` so importing this module does not touch the registry.
    if attr == "app":
        built = make_app()
        globals()["app"] = built
        return built
    raise AttributeError(attr)
