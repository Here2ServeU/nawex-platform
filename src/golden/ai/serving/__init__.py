"""Model serving: KServe Open Inference Protocol (V2) types and the champion fraud-model server."""

from golden.ai.serving.protocol import (
    InferenceError,
    InferRequest,
    InferResponse,
    InferTensor,
    ModelMetadata,
    TensorMetadata,
)
from golden.ai.serving.server import DEFAULT_MODEL, FEATURES_TENSOR, FraudModelServer

__all__ = [
    "DEFAULT_MODEL",
    "FEATURES_TENSOR",
    "FraudModelServer",
    "InferRequest",
    "InferResponse",
    "InferTensor",
    "InferenceError",
    "ModelMetadata",
    "TensorMetadata",
]
