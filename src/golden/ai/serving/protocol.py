"""KServe Open Inference Protocol (OIP, "V2") request/response types.

The V2 protocol is what KServe, NVIDIA Triton, Seldon MLServer and TorchServe speak, so a client written
against it can talk to any of them. REST shape::

    POST /v2/models/{name}/infer
    {"id": "r1", "inputs": [{"name": "features", "shape": [2, 7], "datatype": "FP32", "data": [...]}]}

    -> {"model_name": "fraud-detector", "model_version": "3", "id": "r1",
        "outputs": [{"name": "probability", "shape": [2], "datatype": "FP64", "data": [0.01, 0.93]}]}

``data`` is the row-major flattened tensor. Parsing validates names, datatypes and that the shape's
element count equals ``len(data)``; violations raise :class:`InferenceError` with an HTTP status.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

NUMERIC_DATATYPES = frozenset(
    {"BOOL", "UINT8", "UINT16", "UINT32", "UINT64", "INT8", "INT16", "INT32", "INT64", "FP16", "FP32", "FP64"}
)
DATATYPES = NUMERIC_DATATYPES | {"BYTES"}
MAX_ELEMENTS = 1_000_000


class InferenceError(ValueError):
    """A request the server refuses; ``status`` is the HTTP code to return."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status

    def to_dict(self) -> dict[str, str]:
        return {"error": str(self)}


@dataclass
class InferTensor:
    name: str
    shape: list[int]
    datatype: str
    data: list[Any]
    parameters: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Any) -> InferTensor:
        if not isinstance(d, dict):
            raise InferenceError("each tensor must be an object")
        name, shape, datatype, data = d.get("name"), d.get("shape"), d.get("datatype"), d.get("data")
        if not isinstance(name, str) or not name or len(name) > 128:
            raise InferenceError("tensor 'name' must be a non-empty string (<=128 chars)")
        if not isinstance(shape, list) or not all(isinstance(s, int) and s >= 0 for s in shape):
            raise InferenceError(f"tensor {name!r}: 'shape' must be a list of non-negative ints")
        if datatype not in DATATYPES:
            raise InferenceError(f"tensor {name!r}: unsupported datatype {datatype!r}")
        if not isinstance(data, list):
            raise InferenceError(f"tensor {name!r}: 'data' must be a (flattened) list")
        data = _flatten(data)
        expected = math.prod(shape)
        if expected > MAX_ELEMENTS:
            raise InferenceError(f"tensor {name!r}: {expected} elements exceeds {MAX_ELEMENTS}", 413)
        if expected != len(data):
            raise InferenceError(
                f"tensor {name!r}: shape {shape} has {expected} elements but data has {len(data)}"
            )
        if datatype in NUMERIC_DATATYPES and not all(
            isinstance(x, int | float) and not isinstance(x, str) for x in data
        ):
            raise InferenceError(f"tensor {name!r}: {datatype} data must be numeric")
        return cls(name, list(shape), datatype, data, dict(d.get("parameters") or {}))

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "shape": self.shape,
            "datatype": self.datatype,
            "data": self.data,
        }
        if self.parameters:
            out["parameters"] = self.parameters
        return out


def _flatten(data: list[Any]) -> list[Any]:
    """OIP allows nested row-major lists in JSON; normalise to flat."""
    if not any(isinstance(x, list) for x in data):
        return data
    flat: list[Any] = []
    stack = [iter(data)]
    while stack:
        for x in stack[-1]:
            if isinstance(x, list):
                stack.append(iter(x))
                break
            flat.append(x)
        else:
            stack.pop()
    return flat


@dataclass
class InferRequest:
    inputs: list[InferTensor]
    id: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Any) -> InferRequest:
        if not isinstance(d, dict):
            raise InferenceError("request body must be a JSON object")
        inputs = d.get("inputs")
        if not isinstance(inputs, list) or not inputs:
            raise InferenceError("'inputs' must be a non-empty list")
        tensors = [InferTensor.from_dict(t) for t in inputs]
        names = [t.name for t in tensors]
        if len(set(names)) != len(names):
            raise InferenceError("duplicate input tensor names")
        rid = d.get("id", "")
        if not isinstance(rid, str) or len(rid) > 128:
            raise InferenceError("'id' must be a string (<=128 chars)")
        outputs = [o.get("name") for o in d.get("outputs") or [] if isinstance(o, dict)]
        return cls(tensors, rid, dict(d.get("parameters") or {}), [o for o in outputs if isinstance(o, str)])

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"inputs": [t.to_dict() for t in self.inputs]}
        if self.id:
            out["id"] = self.id
        if self.parameters:
            out["parameters"] = self.parameters
        if self.outputs:
            out["outputs"] = [{"name": n} for n in self.outputs]
        return out


@dataclass
class InferResponse:
    model_name: str
    model_version: str
    outputs: list[InferTensor]
    id: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "outputs": [t.to_dict() for t in self.outputs],
        }
        if self.id:
            out["id"] = self.id
        if self.parameters:
            out["parameters"] = self.parameters
        return out

    def output(self, name: str) -> InferTensor:
        for t in self.outputs:
            if t.name == name:
                return t
        raise KeyError(name)


@dataclass
class TensorMetadata:
    name: str
    datatype: str
    shape: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "datatype": self.datatype, "shape": self.shape}


@dataclass
class ModelMetadata:
    """``GET /v2/models/{name}`` — ``-1`` in a shape is a variable (batch) dimension."""

    name: str
    versions: list[str]
    platform: str
    inputs: list[TensorMetadata]
    outputs: list[TensorMetadata]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "versions": self.versions,
            "platform": self.platform,
            "inputs": [t.to_dict() for t in self.inputs],
            "outputs": [t.to_dict() for t in self.outputs],
        }
