"""Retrieval-augmented generation: chunk → embed → index → retrieve top-k → grounded, cited answer."""

from golden.ai.rag.pipeline import (
    Chunk,
    HashingEmbedder,
    RAGPipeline,
    VectorIndex,
    chunk_text,
    sample_corpus,
)

__all__ = ["Chunk", "HashingEmbedder", "RAGPipeline", "VectorIndex", "chunk_text", "sample_corpus"]
