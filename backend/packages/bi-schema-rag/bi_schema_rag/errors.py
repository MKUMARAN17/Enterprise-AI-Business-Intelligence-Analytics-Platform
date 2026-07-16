"""Exception hierarchy for :mod:`bi_schema_rag`.

Retrieval is a *pre-flight* step for the SQL-generation agent: if the schema
index cannot answer, we would rather raise a typed, catchable error than hand
the agent an empty context and let it hallucinate table names. Every failure
therefore surfaces as a specific subclass of :class:`SchemaRagError`.

:class:`SchemaRagError` subclasses :class:`RuntimeError` (not
:class:`ValueError`) because an unusable index is an operational state of the
retrieval subsystem, not merely a bad argument to a single call — callers that
catch the base class get a clean "retrieval unavailable" boundary.
"""

from __future__ import annotations


class SchemaRagError(RuntimeError):
    """Base class for every error raised by :mod:`bi_schema_rag`.

    Catch this to treat the whole retrieval layer as a single failure domain.
    """


class EmptyIndexError(SchemaRagError):
    """Raised when an index is built from — or queried with — an empty corpus.

    A :class:`~bi_schema_rag.index.SchemaIndex` with no documents can never
    return a relevant schema slice, so we fail loudly at build/retrieve time
    rather than silently returning an empty context that would push the SQL
    agent toward guessing at table and column names.
    """
