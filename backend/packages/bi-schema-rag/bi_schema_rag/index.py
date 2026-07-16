"""The searchable corpus: schema/glossary documents plus their vectors.

:class:`SchemaIndex` is the storage layer that sits between the raw
:mod:`~bi_schema_rag.models` documents and the
:class:`~bi_schema_rag.retriever.SchemaRetriever`. It owns three parallel,
index-aligned lists — the source documents, the rendered text that was
embedded, and the normalized vectors — plus an optional faiss backend.

Why a FAISS-or-pure-Python split lives here: the retriever should not care
*how* nearest neighbours are found, only that it can score a query against the
corpus. So this module hides that decision. If ``faiss`` imports, we build an
``IndexFlatIP`` (inner product over unit vectors == cosine) for fast search on
large catalogs; otherwise we keep the vectors in a plain list and compute
cosine in pure Python. Either way the public ``similarities`` API is identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .embeddings import Embedder, HashingEmbedder
from .errors import EmptyIndexError
from .models import GlossaryDoc, TableDoc

if TYPE_CHECKING:
    from .models import ColumnDoc  # noqa: F401  (re-exported for type-checkers)


def _try_import_faiss() -> object | None:
    """Return the ``faiss`` module if importable, else ``None``.

    Kept as a function (not a module-level import) so that importing this module
    never fails or pays the import cost when faiss is absent — the whole package
    is required to run stdlib-only.
    """
    try:  # pragma: no cover - only taken when faiss-cpu is installed
        import faiss

        return faiss
    except Exception:
        return None


@dataclass(slots=True)
class SchemaIndex:
    """In-memory corpus of embedded schema tables and glossary terms.

    The three ``_``-prefixed sequences are strictly index-aligned: position *i*
    refers to the same logical document across ``_kinds``, ``_names``,
    ``_texts`` and ``_vectors``. ``_faiss`` is populated only when the optional
    backend is available; ``similarities`` transparently uses whichever path
    exists so callers never branch on it.

    This class is not frozen because it is a container built once and then read
    many times; the documents it holds *are* frozen value objects.
    """

    _kinds: list[str]
    _names: list[str]
    _texts: list[str]
    _vectors: list[list[float]]
    _dim: int
    _faiss: object | None = field(default=None, repr=False)

    @classmethod
    def build(
        cls,
        tables: list[TableDoc],
        glossary: list[GlossaryDoc],
        embedder: Embedder | None = None,
    ) -> SchemaIndex:
        """Embed the given tables + glossary into a queryable index.

        Tables are indexed before glossary entries purely for stable, readable
        ordering; ranking is score-driven so order does not affect results. The
        embedder defaults to :class:`HashingEmbedder` so the index builds with
        zero optional dependencies. Raises :class:`EmptyIndexError` when there is
        nothing to index, because an empty index can only ever mislead the SQL
        agent.
        """
        if not tables and not glossary:
            raise EmptyIndexError("cannot build a SchemaIndex from an empty corpus")

        embedder = embedder or HashingEmbedder()

        kinds: list[str] = []
        names: list[str] = []
        texts: list[str] = []
        for table in tables:
            kinds.append("table")
            names.append(table.name)
            texts.append(table.to_document())
        for entry in glossary:
            kinds.append("glossary")
            names.append(entry.term)
            texts.append(entry.to_document())

        vectors = embedder.embed(texts)
        if not vectors or not vectors[0]:
            raise EmptyIndexError("embedder returned empty vectors")
        dim = len(vectors[0])

        faiss_index = cls._maybe_build_faiss(vectors, dim)

        return cls(
            _kinds=kinds,
            _names=names,
            _texts=texts,
            _vectors=vectors,
            _dim=dim,
            _faiss=faiss_index,
        )

    @staticmethod
    def _maybe_build_faiss(vectors: list[list[float]], dim: int) -> object | None:
        """Build an ``IndexFlatIP`` from unit vectors, or ``None`` if faiss absent.

        Inner product on already-L2-normalized vectors equals cosine similarity,
        so ``IndexFlatIP`` gives the same ranking as the pure-Python path while
        scaling to large catalogs. Any faiss/numpy hiccup degrades gracefully to
        the pure-Python fallback rather than breaking index construction.
        """
        faiss = _try_import_faiss()
        if faiss is None:
            return None
        try:  # pragma: no cover - only taken when faiss-cpu is installed
            import numpy as np

            matrix = np.asarray(vectors, dtype="float32")
            flat = faiss.IndexFlatIP(dim)
            flat.add(matrix)
            return flat
        except Exception:
            return None

    def __len__(self) -> int:
        """Number of indexed documents (tables + glossary entries)."""
        return len(self._texts)

    @property
    def dim(self) -> int:
        """Dimensionality of the stored vectors."""
        return self._dim

    def document(self, i: int) -> tuple[str, str, str]:
        """Return ``(kind, name, text)`` for the document at position ``i``."""
        return self._kinds[i], self._names[i], self._texts[i]

    def similarities(self, query_vector: list[float]) -> list[float]:
        """Cosine similarity of ``query_vector`` against every document.

        Returns a list index-aligned with the corpus (position *i* is the score
        for document *i*), so the retriever can blend these with its keyword
        boost without caring whether faiss or pure Python produced them. The
        query vector is expected to be L2-normalized (both embedders emit unit
        vectors); we defensively normalize the pure-Python path anyway.
        """
        if not self._texts:
            raise EmptyIndexError("cannot query an empty SchemaIndex")

        if self._faiss is not None:  # pragma: no cover - faiss-only path
            import numpy as np

            q = np.asarray([query_vector], dtype="float32")
            scores, ids = self._faiss.search(q, len(self._texts))  # type: ignore[attr-defined]
            # faiss returns results sorted by score; scatter them back into
            # corpus order so the return value stays index-aligned.
            ordered = [0.0] * len(self._texts)
            for score, idx in zip(scores[0], ids[0], strict=False):
                if idx >= 0:
                    ordered[int(idx)] = float(score)
            return ordered

        return [self._cosine(query_vector, vec) for vec in self._vectors]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        """Cosine similarity between two equal-length vectors, numpy-free.

        Both operands are normally unit vectors, so this reduces to a dot
        product; dividing by the norms keeps it correct even if a caller passes
        an unnormalized query.
        """
        dot = 0.0
        na = 0.0
        nb = 0.0
        for x, y in zip(a, b, strict=False):
            dot += x * y
            na += x * x
            nb += y * y
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na**0.5 * nb**0.5)
