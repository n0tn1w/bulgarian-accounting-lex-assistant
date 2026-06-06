"""Dense embeddings. Default = bge-m3 (local, multilingual incl. Bulgarian).

The ``Embedder`` ABC isolates the rest of the code from the model choice, so an
OpenAI / other backend can be dropped in later without touching the stores or
retrieval pipeline. The model is loaded lazily on first use.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from config import settings


class Embedder(ABC):
    @property
    @abstractmethod
    def dim(self) -> int: ...

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> List[float]: ...


class BgeEmbedder(Embedder):
    def __init__(self, model_name: str | None = None, batch_size: int | None = None):
        self.model_name = model_name or settings.embedding_model
        self.batch_size = batch_size or settings.embedding_batch_size
        self._model = None  # lazy

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            print(f"  [embed] loading model {self.model_name} ...")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dim(self) -> int:
        return self._ensure_model().get_sentence_embedding_dimension()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        model = self._ensure_model()
        vecs = model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,   # cosine == dot product
            show_progress_bar=True,
            convert_to_numpy=True,
        )
        return vecs.tolist()

    def embed_query(self, text: str) -> List[float]:
        model = self._ensure_model()
        vec = model.encode(
            [text], normalize_embeddings=True, convert_to_numpy=True
        )[0]
        return vec.tolist()
