"""Embedding backends: a deterministic stdlib default and an optional bge model.

The whole package must run in CI and tests with *pure stdlib* — no faiss, no
torch, no sentence-transformers. So the default embedder here,
:class:`HashingEmbedder`, is a self-contained bag-of-words feature-hashing
vectorizer that needs nothing beyond the standard library and still produces
sensible cosine similarities for schema retrieval.

When the ML stack *is* installed, :func:`try_load_bge_embedder` lazily loads a
real ``sentence-transformers`` model for higher-quality semantic matching. The
import is deferred and guarded so that merely importing this module never drags
in heavy optional dependencies.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol, runtime_checkable

# Tokenizer shared by the embedder and the retriever's keyword-overlap boost so
# that "what got embedded" and "what got full-text matched" use identical token
# boundaries. Splits on non-alphanumerics and lowercases; keeps digits because
# schema text contains types like DECIMAL(12,2).
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase-and-split into alphanumeric tokens.

    Exposed at module scope because the retriever's keyword-overlap scoring must
    tokenize queries and documents exactly the way the embedder does; a shared
    function removes any chance of the two drifting apart.
    """
    return _TOKEN_RE.findall(text.lower())


@runtime_checkable
class Embedder(Protocol):
    """Structural contract for anything that turns text into dense vectors.

    Using a :class:`~typing.Protocol` (rather than an ABC) lets a
    ``sentence-transformers`` model, a remote embedding client, or our
    :class:`HashingEmbedder` all satisfy the interface without a shared base
    class — the index only cares that ``embed`` exists and returns row vectors.
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one L2-normalized vector per input string, in order."""
        ...


class HashingEmbedder:
    """Deterministic, dependency-free feature-hashing bag-of-words embedder.

    Each token is hashed into one of ``dim`` buckets (with a sign hash to reduce
    collision bias, the standard "hashing trick"), token counts accumulate into
    the bucket, and the resulting vector is L2-normalized so that dot products
    are cosine similarities. This is intentionally simple: it captures lexical
    overlap between a question and schema text, which — combined with the
    retriever's keyword boost — is enough to route "collection performance by
    branch" to COLLECTIONS + BRANCHES without any learned model.

    Determinism matters: we hash with a fixed algorithm (blake2b over the UTF-8
    token) rather than Python's salted ``hash()`` so vectors are stable across
    processes and runs, which keeps a persisted index valid and makes tests
    reproducible.
    """

    def __init__(self, dim: int = 256) -> None:
        if dim <= 0:
            raise ValueError("dim must be a positive integer")
        self.dim = dim

    def _bucket_and_sign(self, token: str) -> tuple[int, float]:
        """Map a token to (bucket index, +/-1 sign) via a stable digest.

        Two independent bytes of the digest are used so the bucket choice and
        the sign are effectively uncorrelated, which keeps the signed hashing
        trick's collision-cancellation property intact.
        """
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        bucket = value % self.dim
        sign = 1.0 if (value >> 63) & 1 else -1.0
        return bucket, sign

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Vectorize ``texts`` into L2-normalized ``dim``-dimensional rows."""
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in tokenize(text):
                bucket, sign = self._bucket_and_sign(token)
                vec[bucket] += sign
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0.0:
                vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors


def try_load_bge_embedder(model_name: str = "BAAI/bge-small-en-v1.5") -> Embedder | None:
    """Attempt to build a ``sentence-transformers`` bge embedder; ``None`` if unavailable.

    The import is performed *inside* the function so that importing
    :mod:`bi_schema_rag` never requires torch/sentence-transformers. Any failure
    — the package not being installed, or the model weights not being
    downloadable in an offline environment — is swallowed and reported as
    ``None`` so callers can transparently fall back to :class:`HashingEmbedder`.
    """
    try:  # pragma: no cover - exercised only when the ML stack is installed
        from sentence_transformers import SentenceTransformer
    except Exception:
        return None

    try:  # pragma: no cover - requires model weights on disk/network
        model = SentenceTransformer(model_name)
    except Exception:
        return None

    class _BgeEmbedder:
        """Adapter wrapping a loaded SentenceTransformer to the Embedder contract."""

        def __init__(self, st_model: object) -> None:
            self._model = st_model

        def embed(self, texts: list[str]) -> list[list[float]]:
            # normalize_embeddings=True yields unit vectors so downstream cosine
            # / inner-product scoring matches the HashingEmbedder's convention.
            arr = self._model.encode(  # type: ignore[attr-defined]
                texts, normalize_embeddings=True, convert_to_numpy=True
            )
            return [list(map(float, row)) for row in arr]

    return _BgeEmbedder(model)
