"""Schema-aware Retrieval-Augmented Generation for the BI SQL agent.

This package indexes MySQL table/column metadata together with a business
glossary and, given a natural-language question, returns only the relevant
*slice* of the schema. Feeding the SQL-generation agent a focused context —
instead of the entire (potentially hundreds of tables) schema — keeps prompts
small, reduces the chance of the model inventing table/column names, and lets
it join correctly using the retrieved foreign-key hints.

Design contract: the package runs on **pure standard library**. FAISS +
BAAI/bge embeddings are an optional acceleration that is imported lazily; when
they are unavailable the package transparently falls back to a deterministic
hashing embedder and a hybrid vector + keyword retriever, so tests and CI run
without any ML dependency.

Typical use::

    from bi_schema_rag import SchemaIndex, SchemaRetriever, default_catalog

    tables, glossary = default_catalog()
    index = SchemaIndex.build(tables, glossary)
    retriever = SchemaRetriever(index)
    chunks = retriever.retrieve("collection performance by branch", k=6)
    context = SchemaRetriever.format_context(chunks)
"""

from __future__ import annotations

from .catalog import default_catalog
from .embeddings import Embedder, HashingEmbedder, try_load_bge_embedder
from .errors import EmptyIndexError, SchemaRagError
from .index import SchemaIndex
from .models import ColumnDoc, GlossaryDoc, RetrievedChunk, TableDoc
from .retriever import SchemaRetriever

__version__ = "0.1.0"

__all__ = [
    "ColumnDoc",
    "Embedder",
    "EmptyIndexError",
    "GlossaryDoc",
    "HashingEmbedder",
    "RetrievedChunk",
    "SchemaIndex",
    "SchemaRagError",
    "SchemaRetriever",
    "TableDoc",
    "default_catalog",
    "try_load_bge_embedder",
]
