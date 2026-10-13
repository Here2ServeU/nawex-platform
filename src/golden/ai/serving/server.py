"""Model server: serves the registry's ``champion`` fraud model over the Open Inference Protocol.

This is the code a KServe *custom predictor* runs (``deploy/k8s/ml-serving/inferenceservice.yaml``):

* **load**     — resolves ``<model>@<alias>`` through :class:`ModelRegistry` and loads the JSON artifact
  (never pickle). ``ready`` is false until a model is loaded, which keeps the pod out of the Service.
* **reload**   — re-resolves the alias; if the champion moved (promotion or rollback) the new version is
  loaded and swapped in atomically, with no restart. In-flight requests finish on the old model.
* **validate** — accepts either one ``features`` tensor ``[N, F]`` or one ``[N]`` tensor per feature
  name (columnar); rejects wrong names, shapes, non-finite values and one-hot columns outside {0, 1}.
* **batch**    — :meth:`infer_batch` runs several requests as one matrix multiply and splits the
  results back per request; batches above ``max_batch_size`` rows are refused (413).
* **version**  — every response carries ``model_version`` and :meth:`response_headers` returns the
  ``x-model-name`` / ``x-model-version`` headers so callers and logs can attribute every decision.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from golden.ai.lifecycle.fraud_model import CHANNELS, FEATURES, FraudModel
from golden.ai.lifecycle.registry import ModelRegistry
from golden.ai.serving.protocol import (
    InferenceError,
    InferRequest,
    InferResponse,
    InferTensor,
    ModelMetadata,
    TensorMetadata,
)

DEFAULT_MODEL = "fraud-detector"
BINARY_FEATURES = frozenset({*(f"ch_{c}" for c in CHANNELS), "high_risk_country"})
FEATURES_TENSOR = "features"


@dataclass(frozen=True)
class LoadedModel:
    version: int
    model: FraudModel


class FraudModelServer:
    def __init__(
        self,
        registry: ModelRegistry,
        model_name: str = DEFAULT_MODEL,
        *,
        alias: str = "champion",
        max_batch_size: int = 1024,
    ) -> None:
        self.registry = registry
        self.name = model_name
        self.alias = alias
        self.max_batch_size = max_batch_size
        self._loaded: LoadedModel | None = None
        self._lock = threading.Lock()

    # lifecycle --------------------------------------------------------------------------------
    def load(self) -> int:
        """Load the model behind the alias; returns its version. Raises ``KeyError`` if absent."""
        mv = self.registry.get(self.name, self.alias)
        model = FraudModel.load(self._artifact_path(mv.artifact))
        with self._lock:
            self._loaded = LoadedModel(mv.version, model)
        return mv.version

    def _artifact_path(self, artifact: str) -> Path:
        """The registry stores the artifact path as written at registration time; when the registry is
        mounted somewhere else (a PVC or KServe's ``/mnt/models``), resolve it inside the registry root."""
        path = Path(artifact)
        if path.exists():
            return path
        relocated = self.registry.root / self.name / path.name
        if relocated.exists():
            return relocated
        raise FileNotFoundError(f"model artifact {artifact!r} not found (also tried {relocated})")

    def reload(self) -> bool:
        """Swap to the alias's current version if it changed; returns whether a swap happened."""
        try:
            target = self.registry.get(self.name, self.alias).version
        except KeyError:
            return False
        if self._loaded is not None and self._loaded.version == target:
            return False
        self.load()
        return True

    @property
    def ready(self) -> bool:
        return self._loaded is not None

    @property
    def version(self) -> str:
        return str(self._loaded.version) if self._loaded else ""

    def _current(self) -> LoadedModel:
        loaded = self._loaded
        if loaded is None:
            raise InferenceError(f"model {self.name!r} is not loaded", 503)
        return loaded

    def metadata(self) -> ModelMetadata:
        versions = [str(v.version) for v in self.registry.versions(self.name)]
        return ModelMetadata(
            name=self.name,
            versions=versions,
            platform="golden-numpy-logreg",
            inputs=[TensorMetadata(FEATURES_TENSOR, "FP32", [-1, len(FEATURES)])],
            outputs=[
                TensorMetadata("probability", "FP64", [-1]),
                TensorMetadata("is_fraud", "BOOL", [-1]),
            ],
        )

    def response_headers(self, response: InferResponse | None = None) -> dict[str, str]:
        version = response.model_version if response is not None else self.version
        return {"x-model-name": self.name, "x-model-version": version}

    # inference --------------------------------------------------------------------------------
    def to_matrix(self, request: InferRequest) -> np.ndarray:
        """Validate a request's inputs and return an ``[N, F]`` float matrix in ``FEATURES`` order."""
        tensors = {t.name: t for t in request.inputs}
        if FEATURES_TENSOR in tensors:
            if len(tensors) != 1:
                raise InferenceError(f"send either {FEATURES_TENSOR!r} or per-feature tensors, not both")
            t = tensors[FEATURES_TENSOR]
            if len(t.shape) != 2 or t.shape[1] != len(FEATURES):
                raise InferenceError(
                    f"{FEATURES_TENSOR!r} must have shape [N, {len(FEATURES)}]; got {t.shape}"
                )
            x = np.asarray(t.data, dtype=float).reshape(t.shape)
        else:
            unknown = sorted(set(tensors) - set(FEATURES))
            missing = [f for f in FEATURES if f not in tensors]
            if unknown or missing:
                raise InferenceError(f"input tensors: missing {missing}, unknown {unknown}")
            rows = {len(t.data) for t in tensors.values()}
            if len(rows) != 1 or any(len(t.shape) != 1 for t in tensors.values()):
                raise InferenceError("per-feature tensors must all be 1-D with the same length")
            x = np.column_stack([np.asarray(tensors[f].data, dtype=float) for f in FEATURES])
        if x.shape[0] == 0:
            raise InferenceError("empty batch")
        if x.shape[0] > self.max_batch_size:
            raise InferenceError(
                f"batch of {x.shape[0]} rows exceeds max_batch_size {self.max_batch_size}", 413
            )
        if not np.isfinite(x).all():
            raise InferenceError("inputs must be finite (no NaN/inf)")
        for i, f in enumerate(FEATURES):
            if f in BINARY_FEATURES and not np.isin(x[:, i], (0.0, 1.0)).all():
                raise InferenceError(f"feature {f!r} is one-hot and must be 0 or 1")
        return x

    def _respond(self, request: InferRequest, loaded: LoadedModel, probs: np.ndarray) -> InferResponse:
        n = len(probs)
        outputs = [
            InferTensor("probability", [n], "FP64", [round(float(p), 6) for p in probs]),
            InferTensor("is_fraud", [n], "BOOL", [bool(p >= loaded.model.threshold) for p in probs]),
        ]
        if request.outputs:
            wanted = set(request.outputs)
            outputs = [o for o in outputs if o.name in wanted]
            if not outputs:
                raise InferenceError(f"unknown requested outputs {sorted(wanted)}")
        return InferResponse(
            model_name=self.name,
            model_version=str(loaded.version),
            outputs=outputs,
            id=request.id,
            parameters={"threshold": loaded.model.threshold},
        )

    def infer(self, request: InferRequest | dict[str, Any]) -> InferResponse:
        req = request if isinstance(request, InferRequest) else InferRequest.from_dict(request)
        loaded = self._current()
        x = self.to_matrix(req)
        return self._respond(req, loaded, loaded.model.predict_proba(x))

    def infer_batch(self, requests: list[InferRequest]) -> list[InferResponse]:
        """Server-side batching: one forward pass for many requests, all on the same model version."""
        if not requests:
            return []
        loaded = self._current()
        mats = [self.to_matrix(r) for r in requests]
        total = sum(m.shape[0] for m in mats)
        if total > self.max_batch_size:
            raise InferenceError(f"combined batch of {total} rows exceeds {self.max_batch_size}", 413)
        probs = loaded.model.predict_proba(np.vstack(mats))
        out, start = [], 0
        for req, m in zip(requests, mats, strict=True):
            out.append(self._respond(req, loaded, probs[start : start + m.shape[0]]))
            start += m.shape[0]
        return out
